"""上下文窗口管理器

核心职责：
1. 路由：user_id + chat_key → context_id
2. 锚定：更新上下文窗口的 active_dialog_id
3. 消息注入：将新聊天消息注入上下文历史（含群聊 8 条防爆）
4. 历史获取：返回 IR 格式的 MessageTurn 列表
5. 压缩管理：触发 timeline 压缩 + 应用已就绪的摘要
6. 重启恢复：从 DB 重建内存态
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
import mimetypes
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.core.runtime_identity import (
    get_bot_persona_display_name,
    get_primary_advanced_user_display_name,
    get_primary_advanced_user_id,
    is_advanced_user_id,
)
from holo_cortex_zero.models.db_context_window import DBContextDialogState, DBContextMessage, DBContextWindow
from holo_cortex_zero.schemas.ir import MessagePart, MessageTurn, ToolCall
from holo_cortex_zero.services.agent.resolver import normalize_bot_surface_text
from holo_cortex_zero.services.file_system.quarantine import quarantine_file_service
from tortoise import Tortoise
from tortoise.transactions import in_transaction


class ContextWindowManager:
    """上下文窗口生命周期管理"""

    # 全局正则：彻底清除 [数字|名字] 格式前缀，防止 bot 模仿
    _ID_NAME_PATTERN = re.compile(r'\[[\d]+\|[^\]]+\]\s*')
    _RISK_DISPLAY_NAME = "风险用户"
    _NORMAL_CONTEXT_ARCHIVE_SAMPLE_STRIDE = 5
    _NORMAL_CONTEXT_ARCHIVE_MAX_BLOCKS = 6
    _NORMAL_CONTEXT_ARCHIVE_HEADER_PREFIX = "【较早历史归档 "

    def __init__(self) -> None:
        # 内存缓存: context_id → DBContextWindow
        self._windows: Dict[str, DBContextWindow] = {}
        # 已注入消息的 source_message_id 集合，防止重复注入
        self._injected_msg_ids: Dict[str, Set[str]] = {}
        # 普通 context 归档锁：仅保护当前进程内同一 context 的归档回收
        self._normal_context_archive_locks: Dict[str, asyncio.Lock] = {}
        # 配置（运行时从 yaml 读取）
        self.advanced_user_id: str = get_primary_advanced_user_id(config)
        self.group_chat_max_inject: int = 8

    async def _get_window(self, context_id: str) -> Optional[DBContextWindow]:
        window = self._windows.get(context_id)
        if window:
            return window
        window = await DBContextWindow.get_or_none(context_id=context_id)
        if window:
            self._windows[context_id] = window
        return window

    async def _is_normal_context(self, context_id: str) -> bool:
        window = await self._get_window(context_id)
        return bool(window and str(window.owner_type or "") == "normal")

    def _get_normal_context_archive_lock(self, context_id: str) -> asyncio.Lock:
        """获取普通 context 归档锁。

        仅覆盖当前进程内的同一 context 归档回收，避免重复归档。
        """
        lock = self._normal_context_archive_locks.get(context_id)
        if lock is None:
            lock = asyncio.Lock()
            self._normal_context_archive_locks[context_id] = lock
        return lock

    @staticmethod
    def _get_normal_context_reset_threshold() -> int:
        return max(1, int(getattr(config, "NORMAL_CONTEXT_RESET_THRESHOLD_MESSAGES", 48) or 48))

    @staticmethod
    def _get_normal_context_reset_keep() -> int:
        return max(1, int(getattr(config, "NORMAL_CONTEXT_RESET_KEEP_MESSAGES", 10) or 10))

    @property
    def max_history_before_compress(self) -> int:
        return max(1, int(getattr(config, "ADVANCED_CONTEXT_MAX_HISTORY_BEFORE_COMPRESS", 100) or 100))

    @property
    def keep_recent_after_compress(self) -> int:
        return max(1, int(getattr(config, "ADVANCED_CONTEXT_KEEP_RECENT_AFTER_COMPRESS", 10) or 10))

    @property
    def hard_limit_ratio(self) -> float:
        try:
            ratio = float(getattr(config, "ADVANCED_CONTEXT_HARD_LIMIT_RATIO", 1.2) or 1.2)
        except Exception:
            ratio = 1.2
        return max(1.0, ratio)

    async def _get_or_bootstrap_dialog_state(
        self,
        context_id: str,
        dialog_chat_key: str,
    ) -> DBContextDialogState:
        """获取某个对话窗口的同步状态。

        首次迁移时，允许从旧的 context_message 投影反推出一个兼容水位，
        之后只信任独立的 dialog state，不再把上下文历史误当同步游标。
        """
        state = await DBContextDialogState.get_or_none(
            context_id=context_id,
            dialog_chat_key=dialog_chat_key,
        )
        if state:
            return state

        legacy_last_synced_db_id = await self._get_legacy_dialog_last_synced_db_id(
            context_id=context_id,
            dialog_chat_key=dialog_chat_key,
        )
        state = await DBContextDialogState.create(
            context_id=context_id,
            dialog_chat_key=dialog_chat_key,
            last_synced_db_id=legacy_last_synced_db_id,
        )
        logger.info(
            f"上下文窗口 {context_id} 初始化对话同步水位: dialog={dialog_chat_key} "
            f"last_synced_db_id={legacy_last_synced_db_id} (legacy_bootstrap)"
        )
        return state

    async def _get_legacy_dialog_last_synced_db_id(self, context_id: str, dialog_chat_key: str) -> int:
        """兼容旧逻辑：从 context_message 投影反推对话同步水位。"""
        from holo_cortex_zero.models.db_chat_message import DBChatMessage

        source_ids = await DBContextMessage.filter(
            context_id=context_id,
            source_chat_key=dialog_chat_key,
        ).values_list("source_message_id", flat=True)

        db_ids: List[int] = []
        message_ids: List[str] = []
        for raw in source_ids:
            sid = self._normalize_source_message_id(raw)
            if not sid:
                continue
            if sid.startswith("dbid_"):
                try:
                    db_ids.append(int(sid[5:]))
                except ValueError:
                    continue
            else:
                message_ids.append(sid)

        max_db_id = max(db_ids) if db_ids else 0
        if message_ids:
            latest = await DBChatMessage.filter(
                chat_key=dialog_chat_key,
                message_id__in=message_ids,
            ).order_by("-id").first()
            if latest:
                max_db_id = max(max_db_id, int(latest.id))

        return max_db_id

    async def _get_dialog_last_synced_db_id(self, context_id: str, dialog_chat_key: str) -> int:
        """获取某个对话窗口已同步到的最新 DBChatMessage.id。"""
        state = await self._get_or_bootstrap_dialog_state(context_id, dialog_chat_key)
        return int(state.last_synced_db_id or 0)

    async def _set_dialog_last_synced_db_id(
        self,
        context_id: str,
        dialog_chat_key: str,
        last_synced_db_id: int,
    ) -> None:
        """更新某个对话窗口的独立同步水位。"""
        state = await self._get_or_bootstrap_dialog_state(context_id, dialog_chat_key)
        if last_synced_db_id <= int(state.last_synced_db_id or 0):
            return
        state.last_synced_db_id = int(last_synced_db_id)
        await state.save(update_fields=["last_synced_db_id", "updated_at"])
        logger.debug(
            f"上下文窗口 {context_id} 更新对话同步水位: dialog={dialog_chat_key} "
            f"last_synced_db_id={last_synced_db_id}"
        )

    @staticmethod
    def _normalize_source_message_id(raw: Any) -> str:
        """归一化 source_message_id，去掉拆分后缀。"""
        sid = str(raw or "").strip()
        if not sid:
            return ""
        return sid.split("#", 1)[0]

    @staticmethod
    def _format_db_msg_timestamp(db_msg: Any) -> str:
        """格式化聊天消息时间，优先使用发送时间戳。"""
        dt_value: Optional[datetime] = None

        send_timestamp = getattr(db_msg, "send_timestamp", None)
        if send_timestamp:
            try:
                dt_value = datetime.fromtimestamp(int(send_timestamp))
            except Exception:
                dt_value = None

        if dt_value is None:
            for attr_name in ("create_time", "created_at", "update_time"):
                raw_value = getattr(db_msg, attr_name, None)
                if isinstance(raw_value, datetime):
                    dt_value = raw_value
                    break

        return dt_value.strftime("%Y-%m-%d %H:%M:%S") if dt_value else ""

    @classmethod
    def _sanitize_sender_name_for_context(cls, sender_id: Any, sender_name: Any) -> str:
        normalized_sender_id = str(sender_id or "").strip()
        normalized_sender_name = str(sender_name or "").strip()
        protected_display_name = get_primary_advanced_user_display_name(config)
        if (
            normalized_sender_name == protected_display_name
            and normalized_sender_id != get_primary_advanced_user_id(config)
        ):
            logger.warning(
                "上下文发送者名称命中受保护别名，已兜底清洗: sender_id=%s raw_sender_name=%r sanitized=%s",
                normalized_sender_id,
                normalized_sender_name,
                cls._RISK_DISPLAY_NAME,
            )
            return cls._RISK_DISPLAY_NAME
        return normalized_sender_name

    def _build_db_msg_prefix(self, db_msg: Any) -> str:
        """构建聊天记录的发送者前缀。"""
        uid = str(getattr(db_msg, "platform_userid", "") or getattr(db_msg, "sender_id", "") or "").strip()
        if not uid:
            return ""

        nickname = self._sanitize_sender_name_for_context(
            uid,
            getattr(db_msg, "sender_nickname", "")
            or getattr(db_msg, "sender_name", "")
            or uid,
        ).strip()
        ts = self._format_db_msg_timestamp(db_msg)
        return f"¥{nickname}¥{ts}¥{uid}¥说：" if ts else f"¥{nickname}¥{uid}¥说："

    @staticmethod
    def _parse_json_dict(raw_value: Any) -> Dict[str, Any]:
        if isinstance(raw_value, dict):
            return dict(raw_value)

        text = str(raw_value or "").strip()
        if not text:
            return {}

        try:
            parsed = json.loads(text)
        except Exception:
            return {}

        return dict(parsed) if isinstance(parsed, dict) else {}

    @classmethod
    def _merge_notice_prefix(cls, notice_prefix: str, text: str) -> str:
        normalized_notice = str(notice_prefix or "").strip()
        normalized_text = str(text or "")
        if not normalized_notice:
            return normalized_text
        if normalized_text.startswith(normalized_notice):
            return normalized_text
        return f"{normalized_notice}{normalized_text}"

    @staticmethod
    def _is_group_chat_key(chat_key: str) -> bool:
        normalized = str(chat_key or "").strip()
        return bool(normalized) and "-group_" in normalized

    @staticmethod
    def is_group_chat_key(chat_key: str) -> bool:
        return ContextWindowManager._is_group_chat_key(chat_key)

    @staticmethod
    def infer_dialog_chat_type(chat_key: str) -> str:
        normalized = str(chat_key or "").strip().lower()
        if "-group_" in normalized:
            return "group"
        if "-private_" in normalized:
            return "private"
        return ""

    @staticmethod
    def is_advanced_window(window: Optional[DBContextWindow]) -> bool:
        return bool(window and str(window.owner_type or "") == "advanced")

    @staticmethod
    def _normalize_advanced_mode(mode: Any) -> str:
        from holo_cortex_zero.services.advanced_context_mode import advanced_context_mode_service

        return advanced_context_mode_service.normalize_mode(mode)

    def get_default_advanced_mode_for_chat(self, chat_key: str, chat_type: Optional[str] = None) -> str:
        normalized_chat_type = str(chat_type or "").strip().lower()
        if not normalized_chat_type:
            normalized_chat_type = self.infer_dialog_chat_type(chat_key)

        if normalized_chat_type == "private" or normalized_chat_type.endswith(".private"):
            configured = str(getattr(config, "ADVANCED_CONTEXT_PRIVATE_DEFAULT_MODE", "deek") or "deek")
            return self._normalize_advanced_mode(configured) or "deek"
        if normalized_chat_type == "group" or normalized_chat_type.endswith(".group"):
            configured = str(getattr(config, "ADVANCED_CONTEXT_GROUP_DEFAULT_MODE", "norm") or "norm")
            return self._normalize_advanced_mode(configured) or "norm"
        return "norm"

    async def ensure_schema_columns(self) -> None:
        conn = Tortoise.get_connection("default")
        ddl_statements = [
            'ALTER TABLE "context_window" ADD COLUMN IF NOT EXISTS "advanced_context_mode" VARCHAR(32) NOT NULL DEFAULT \'norm\'',
            'ALTER TABLE "context_window" ADD COLUMN IF NOT EXISTS "advanced_context_mode_source" VARCHAR(32) NOT NULL DEFAULT \'default\'',
        ]
        for sql in ddl_statements:
            await conn.execute_query(sql)

        windows = await DBContextWindow.filter(owner_type="advanced").all()
        fixed = 0
        for window in windows:
            current_mode = self._normalize_advanced_mode(getattr(window, "advanced_context_mode", ""))
            current_source = str(getattr(window, "advanced_context_mode_source", "") or "").strip()
            changed = False
            if not current_mode:
                window.advanced_context_mode = self.get_default_advanced_mode_for_chat(window.active_dialog_id)
                changed = True
            elif current_source == "default":
                default_mode = self.get_default_advanced_mode_for_chat(window.active_dialog_id)
                if default_mode and current_mode != default_mode:
                    window.advanced_context_mode = default_mode
                    changed = True
            elif current_mode != str(getattr(window, "advanced_context_mode", "") or ""):
                window.advanced_context_mode = current_mode
                changed = True
            if current_source not in {"default", "manual"}:
                window.advanced_context_mode_source = "default"
                changed = True
            if changed:
                await window.save(update_fields=["advanced_context_mode", "advanced_context_mode_source", "updated_at"])
                self._windows[window.context_id] = window
                fixed += 1
        logger.info(f"advanced context mode schema 检查完成: advanced_windows={len(windows)} fixed={fixed}")

    async def set_advanced_context_mode(
        self,
        window: DBContextWindow,
        *,
        mode: str,
        source: str,
        dialog_chat_key: Optional[str] = None,
    ) -> bool:
        if not self.is_advanced_window(window):
            return False

        normalized_mode = self._normalize_advanced_mode(mode)
        if not normalized_mode:
            logger.warning(
                "advanced context mode set 跳过非法模式: "
                f"ctx={getattr(window, 'context_id', '')} raw_mode={mode!r} source={source}"
            )
            return False

        normalized_source = str(source or "default").strip() or "default"
        if normalized_source not in {"default", "manual"}:
            normalized_source = "default"

        changed = False
        if str(window.advanced_context_mode or "") != normalized_mode:
            window.advanced_context_mode = normalized_mode
            changed = True
        if str(window.advanced_context_mode_source or "") != normalized_source:
            window.advanced_context_mode_source = normalized_source
            changed = True
        if dialog_chat_key is not None and str(window.active_dialog_id or "") != str(dialog_chat_key or ""):
            window.active_dialog_id = str(dialog_chat_key or "")
            changed = True

        if changed:
            await window.save(update_fields=["advanced_context_mode", "advanced_context_mode_source", "active_dialog_id", "updated_at"])
            self._windows[window.context_id] = window
            logger.info(
                "advanced context mode updated: "
                f"ctx={window.context_id} mode={window.advanced_context_mode} "
                f"source={window.advanced_context_mode_source} active_dialog={window.active_dialog_id}"
            )
        return changed

    async def apply_advanced_dialog_default_if_needed(
        self,
        window: DBContextWindow,
        *,
        dialog_chat_key: str,
        chat_type: Optional[str] = None,
    ) -> bool:
        if not self.is_advanced_window(window):
            return False

        current_mode = self._normalize_advanced_mode(getattr(window, "advanced_context_mode", ""))
        active_dialog_id = str(window.active_dialog_id or "")
        should_apply_default = not active_dialog_id or active_dialog_id != str(dialog_chat_key or "") or not current_mode
        if not should_apply_default:
            return False

        default_mode = self.get_default_advanced_mode_for_chat(dialog_chat_key, chat_type=chat_type)
        await self.set_advanced_context_mode(
            window,
            mode=default_mode,
            source="default",
            dialog_chat_key=dialog_chat_key,
        )
        logger.info(
            "advanced context dialog default applied: "
            f"ctx={window.context_id} chat={dialog_chat_key} old_active={active_dialog_id or '<empty>'} "
            f"mode={default_mode} "
            f"reason={'invalid_mode' if active_dialog_id == str(dialog_chat_key or '') and not current_mode else 'dialog_switch'}"
        )
        return True

    async def has_any_tool_chain_active(self) -> bool:
        cached_active = any(bool(getattr(window, "tool_chain_active", False)) for window in self._windows.values())
        if cached_active:
            return True
        active_count = await DBContextWindow.filter(tool_chain_active=True).count()
        return active_count > 0

    async def clear_all_message_and_context_records(
        self,
        window: DBContextWindow,
        *,
        dialog_chat_key: str,
        clear_compressed_summary: bool = False,
    ) -> Dict[str, Any]:
        """清空全局消息记录和 context 消息。

        触发入口仍只允许高级 context；执行范围是全局 chat_message、context_message、
        context_dialog_state，并重置所有 context_window 的 timeline 计数、运行态与自动记忆计数。
        主干保持一套清理流程：/clear 保留已落地的 compressed_summary；/clearall 额外清空它。
        """
        if not self.is_advanced_window(window):
            return {
                "applied": False,
                "reason": "not_advanced",
                "context_messages_deleted": 0,
                "chat_messages_deleted": 0,
                "dialog_states_deleted": 0,
                "windows_reset": 0,
                "compressed_summaries_cleared": 0,
            }

        from holo_cortex_zero.models.db_chat_message import DBChatMessage

        context_id = str(window.context_id or "").strip()
        context_messages_deleted = await DBContextMessage.all().delete()
        dialog_states_deleted = await DBContextDialogState.all().delete()
        chat_messages_deleted = await DBChatMessage.all().delete()

        windows = await DBContextWindow.all()
        reset_fields = [
            "last_compress_version",
            "msg_count_since_compress",
            "summary_generating",
            "pending_summary",
            "pending_summary_ready",
            "auto_memory_last_context_msg_id",
            "auto_memory_pending_count",
            "auto_memory_generating",
            "updated_at",
        ]
        if clear_compressed_summary:
            reset_fields.append("compressed_summary")

        compressed_summaries_cleared = 0
        for item in windows:
            if clear_compressed_summary:
                if str(item.compressed_summary or "").strip():
                    compressed_summaries_cleared += 1
                item.compressed_summary = ""
            item.last_compress_version = 0
            item.msg_count_since_compress = 0
            item.summary_generating = False
            item.pending_summary = ""
            item.pending_summary_ready = False
            item.auto_memory_last_context_msg_id = 0
            item.auto_memory_pending_count = 0
            item.auto_memory_generating = False
            await item.save(update_fields=reset_fields)
            self._windows[item.context_id] = item

        self._injected_msg_ids.clear()
        self._normal_context_archive_locks.clear()

        result = {
            "applied": True,
            "reason": "cleared_all",
            "context_messages_deleted": int(context_messages_deleted or 0),
            "chat_messages_deleted": int(chat_messages_deleted or 0),
            "dialog_states_deleted": int(dialog_states_deleted or 0),
            "windows_reset": len(windows),
            "compressed_summaries_cleared": compressed_summaries_cleared,
        }
        logger.info(
            "advanced context clear all records completed: "
            f"ctx={context_id} chat={dialog_chat_key} "
            f"clear_compressed_summary={clear_compressed_summary} "
            f"context_messages={result['context_messages_deleted']} "
            f"chat_messages={result['chat_messages_deleted']} "
            f"dialog_states={result['dialog_states_deleted']} "
            f"compressed_summaries_cleared={result['compressed_summaries_cleared']} "
            f"windows_reset={result['windows_reset']}"
        )
        return result

    @classmethod
    def _text_has_group_trigger_notice(cls, text: str) -> bool:
        normalized = str(text or "")
        if not normalized:
            return False
        if normalized.startswith("@你；"):
            return True
        return cls._looks_like_prefixed_chat_line(normalized) and "¥说：@你；" in normalized

    @classmethod
    def _parts_have_group_trigger_notice(cls, parts: List[MessagePart]) -> bool:
        for part in parts:
            if part.type != "text":
                continue
            if cls._text_has_group_trigger_notice(str(part.text or "")):
                return True
        return False

    @classmethod
    def _strip_group_trigger_notice_text(cls, text: str) -> str:
        normalized = str(text or "")
        if not normalized:
            return normalized
        if normalized.startswith("@你；"):
            return normalized[len("@你；"):]
        if cls._looks_like_prefixed_chat_line(normalized) and "¥说：@你；" in normalized:
            return normalized.replace("¥说：@你；", "¥说：", 1)
        return normalized

    @classmethod
    def _normalize_history_group_trigger_notice_parts(
        cls,
        parts: List[MessagePart],
        *,
        keep_notice: bool,
    ) -> tuple[List[MessagePart], int]:
        if keep_notice:
            return parts, 0

        stripped_count = 0
        for part in parts:
            if part.type != "text":
                continue
            current_text = str(part.text or "")
            stripped_text = cls._strip_group_trigger_notice_text(current_text)
            if stripped_text == current_text:
                continue
            part.text = stripped_text
            stripped_count += 1

        return parts, stripped_count

    @classmethod
    def _extract_db_msg_context_notice_prefix(cls, db_msg: Any) -> str:
        ext_data = cls._parse_json_dict(getattr(db_msg, "ext_data", ""))
        context_notice = ext_data.get("context_notice")
        if not isinstance(context_notice, dict):
            return ""
        return str(context_notice.get("prefix", "") or "").strip()

    @classmethod
    def _apply_notice_prefix_to_parts(cls, parts: List[MessagePart], notice_prefix: str) -> List[MessagePart]:
        normalized_notice = str(notice_prefix or "").strip()
        if not normalized_notice:
            return parts

        if not parts:
            return [MessagePart(type="text", text=normalized_notice)]

        for part in parts:
            if part.type != "text":
                continue
            current_text = str(part.text or "")
            if current_text.startswith(normalized_notice):
                return parts
            part.text = f"{normalized_notice}{current_text}"
            return parts

        return [MessagePart(type="text", text=normalized_notice), *parts]

    @staticmethod
    def _format_context_msg_timestamp(ctx_msg: Any) -> str:
        """格式化 DBContextMessage 时间。"""
        dt_value = getattr(ctx_msg, "created_at", None)
        if isinstance(dt_value, datetime):
            return dt_value.strftime("%Y-%m-%d %H:%M:%S")
        return ""

    @classmethod
    def _extract_archive_texts_from_parts_json(cls, parts_json: str) -> List[str]:
        """仅提取适合普通 context 归档的纯文本 part。"""
        if not parts_json or parts_json == "[]":
            return []

        try:
            items = json.loads(parts_json)
        except json.JSONDecodeError:
            return []

        texts: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("type", "text")) != "text":
                continue

            raw_text = item.get("text")
            if not isinstance(raw_text, str):
                continue

            cleaned_text = cls._sanitize_text(raw_text)
            if cleaned_text:
                texts.append(cleaned_text)

        return texts

    @classmethod
    def _looks_like_prefixed_chat_line(cls, text: str) -> bool:
        """判断文本是否已是 ¥昵称¥时间¥ID¥说： 格式。"""
        normalized = str(text or "").strip()
        return normalized.startswith("¥") and "¥说：" in normalized

    def _build_context_msg_prefix(self, ctx_msg: Any) -> str:
        """为归档文本补齐统一的 ¥ 前缀。"""
        sender_id = str(getattr(ctx_msg, "sender_id", "") or "").strip()
        role = str(getattr(ctx_msg, "role", "") or "").strip()
        if not sender_id:
            sender_id = "-1" if role == "assistant" else "0"
        sender_name = str(getattr(ctx_msg, "sender_name", "") or "").strip()
        if not sender_name:
            if role == "assistant":
                sender_name = get_bot_persona_display_name(config)
            elif role == "tool":
                sender_name = "Tool"
            else:
                sender_name = sender_id or "未知"

        ts = self._format_context_msg_timestamp(ctx_msg)
        return f"¥{sender_name}¥{ts}¥{sender_id}¥说：" if ts else f"¥{sender_name}¥{sender_id}¥说："

    def _render_archive_line_from_context_msg(self, ctx_msg: DBContextMessage) -> str:
        """将 DBContextMessage 渲染为普通 context 归档行。"""
        if str(ctx_msg.msg_type or "") == "history_only":
            return ""
        if str(ctx_msg.role or "") not in {"user", "assistant"}:
            return ""

        text_parts = self._extract_archive_texts_from_parts_json(ctx_msg.parts_json)
        if not text_parts:
            return ""

        merged_text = "\n".join(part.strip() for part in text_parts if str(part or "").strip()).strip()
        if not merged_text:
            return ""

        if self._looks_like_prefixed_chat_line(merged_text):
            return merged_text

        return f"{self._build_context_msg_prefix(ctx_msg)}{merged_text}"

    @classmethod
    def _sample_archive_lines(cls, lines: List[str]) -> List[str]:
        """确定性抽取普通 context 的历史残影。"""
        normalized_lines = [str(line or "").strip() for line in lines if str(line or "").strip()]
        if len(normalized_lines) <= 2:
            return normalized_lines

        selected_indexes = set(range(0, len(normalized_lines), cls._NORMAL_CONTEXT_ARCHIVE_SAMPLE_STRIDE))
        selected_indexes.add(len(normalized_lines) - 1)
        return [normalized_lines[idx] for idx in sorted(selected_indexes)]

    @classmethod
    def _split_normal_context_archive_blocks(cls, archive_text: str) -> List[str]:
        """按块拆分普通 context 的历史归档文本。"""
        normalized = str(archive_text or "").strip()
        if not normalized:
            return []

        blocks: List[str] = []
        current_lines: List[str] = []
        for line in normalized.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith(cls._NORMAL_CONTEXT_ARCHIVE_HEADER_PREFIX):
                if current_lines:
                    block = "\n".join(current_lines).strip()
                    if block:
                        blocks.append(block)
                current_lines = [stripped_line]
                continue

            if current_lines:
                current_lines.append(line)
            else:
                current_lines = [line]

        if current_lines:
            block = "\n".join(current_lines).strip()
            if block:
                blocks.append(block)

        return blocks

    @classmethod
    def _merge_normal_context_archive_blocks(cls, existing_archive: str, new_block: str) -> str:
        """追加并裁剪普通 context 归档块。"""
        blocks = cls._split_normal_context_archive_blocks(existing_archive)
        normalized_block = str(new_block or "").strip()
        if normalized_block:
            blocks.append(normalized_block)
        if len(blocks) > cls._NORMAL_CONTEXT_ARCHIVE_MAX_BLOCKS:
            blocks = blocks[-cls._NORMAL_CONTEXT_ARCHIVE_MAX_BLOCKS:]
        return "\n\n".join(block for block in blocks if block).strip()

    def _build_normal_context_archive_block(
        self,
        sampled_lines: List[str],
        *,
        source_line_count: int,
    ) -> str:
        """构建普通 context 的纯文本归档块。"""
        if not sampled_lines:
            return ""

        header = (
            f"{self._NORMAL_CONTEXT_ARCHIVE_HEADER_PREFIX}"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {len(sampled_lines)}/{source_line_count}】"
        )
        return f"{header}\n" + "\n".join(sampled_lines)

    async def _archive_normal_context_history(self, context_id: str, *, threshold: int, keep_recent: int) -> int:
        """普通 context 到阈值后：抽样旧前缀为纯文本归档，再回收原历史。"""
        batch_size = max(1, threshold - keep_recent)
        deleted_total = 0
        loop_count = 0

        while loop_count < 8:
            archive_line_count = 0
            sampled_line_count = 0
            deleted = 0

            async with in_transaction() as conn:
                total = await DBContextMessage.filter(context_id=context_id).using_db(conn).count()
                if total < threshold:
                    break

                deletable_count = total - keep_recent
                if deletable_count <= 0:
                    break

                current_batch_size = min(batch_size, deletable_count)
                archive_batch = (
                    await DBContextMessage.filter(context_id=context_id)
                    .using_db(conn)
                    .order_by("id")
                    .limit(current_batch_size)
                    .all()
                )
                if not archive_batch:
                    break

                archive_lines: List[str] = []
                archive_ids: List[int] = []
                for ctx_msg in archive_batch:
                    archive_ids.append(int(ctx_msg.id))
                    rendered_line = self._render_archive_line_from_context_msg(ctx_msg)
                    if rendered_line:
                        archive_lines.append(rendered_line)

                archive_line_count = len(archive_lines)

                if archive_lines:
                    sampled_lines = self._sample_archive_lines(archive_lines)
                    sampled_line_count = len(sampled_lines)
                    archive_block = self._build_normal_context_archive_block(
                        sampled_lines,
                        source_line_count=archive_line_count,
                    )
                    if not archive_block:
                        logger.warning(
                            "普通 context 历史归档块为空，已中止删除: ctx=%s batch=%s source_lines=%s",
                            context_id,
                            loop_count + 1,
                            archive_line_count,
                        )
                        return deleted_total

                    window = await DBContextWindow.get_or_none(context_id=context_id).using_db(conn)
                    if not window:
                        logger.warning(
                            "普通 context 历史归档缺少窗口，已中止删除: ctx=%s batch=%s",
                            context_id,
                            loop_count + 1,
                        )
                        return deleted_total

                    merged_archive = self._merge_normal_context_archive_blocks(
                        window.compressed_summary,
                        archive_block,
                    )
                    if merged_archive != str(window.compressed_summary or ""):
                        window.compressed_summary = merged_archive
                        await window.save(using_db=conn, update_fields=["compressed_summary", "updated_at"])
                    self._windows[context_id] = window
                else:
                    logger.info(
                        "普通 context 历史归档批次无文本，执行纯清理: ctx=%s batch=%s candidates=%s",
                        context_id,
                        loop_count + 1,
                        len(archive_batch),
                    )

                deleted = await DBContextMessage.filter(id__in=archive_ids).using_db(conn).delete()
                deleted_total += int(deleted or 0)
                total = await DBContextMessage.filter(context_id=context_id).using_db(conn).count()

            loop_count += 1
            logger.info(
                "普通 context 历史归档完成: ctx=%s batch=%s source_lines=%s sampled_lines=%s deleted=%s remain=%s",
                context_id,
                loop_count,
                archive_line_count,
                sampled_line_count,
                deleted,
                total,
            )

        final_total = await DBContextMessage.filter(context_id=context_id).count()
        if final_total >= threshold:
            logger.warning(
                "普通 context 历史归档后仍高于阈值: ctx=%s threshold=%s remain=%s loops=%s",
                context_id,
                threshold,
                final_total,
                loop_count,
            )

        return deleted_total

    async def enforce_history_hard_limit(self, context_id: str) -> int:
        """上下文窗口硬限制：超过 120 条时滑动删除最旧消息。"""
        if await self._is_normal_context(context_id):
            threshold = self._get_normal_context_reset_threshold()
            keep_recent = min(self._get_normal_context_reset_keep(), threshold)
            archive_lock = self._get_normal_context_archive_lock(context_id)
            async with archive_lock:
                deleted = await self._archive_normal_context_history(
                    context_id,
                    threshold=threshold,
                    keep_recent=keep_recent,
                )
            if deleted > 0:
                logger.info(
                    "普通 context 达到重置阈值，执行归档式历史回收: ctx=%s threshold=%s keep=%s deleted=%s",
                    context_id,
                    threshold,
                    keep_recent,
                    deleted,
                )
            return deleted

        hard_limit = int(self.max_history_before_compress * self.hard_limit_ratio)
        total = await DBContextMessage.filter(context_id=context_id).count()
        if total <= hard_limit:
            return 0

        keep_ids = (
            await DBContextMessage.filter(context_id=context_id)
            .order_by("-id")
            .limit(hard_limit)
            .values_list("id", flat=True)
        )
        deleted = await DBContextMessage.filter(context_id=context_id).exclude(id__in=keep_ids).delete()
        logger.warning(f"上下文窗口 {context_id} 超出硬上限 {hard_limit}，滑动删除最旧 {deleted} 条")
        return int(deleted or 0)

    @staticmethod
    def _is_system_db_msg(db_msg: Any) -> bool:
        """判断 DBChatMessage 是否为真正的系统消息。

        当前库里 bot 回复与 system 通知都会写成 `sender_id=-1`，
        这里只把 platform_userid=0 或显式 SYSTEM 名称视为 system，
        避免 bot 回复在同步链中被误跳过。
        """
        sender_id = str(getattr(db_msg, "sender_id", "") or "").strip()
        if sender_id != "-1":
            return False

        platform_userid = str(getattr(db_msg, "platform_userid", "") or "").strip()
        sender_name = str(getattr(db_msg, "sender_name", "") or "").strip().upper()
        sender_nickname = str(getattr(db_msg, "sender_nickname", "") or "").strip().upper()
        return platform_userid == "0" or (
            sender_name == "SYSTEM" and sender_nickname == "SYSTEM"
        )

    # ── 核心路由 ──

    async def resolve_context_window(
        self,
        user_id: str,
        chat_key: str,
        adapter_key: str = "",
    ) -> DBContextWindow:
        """核心路由：确定用户的上下文窗口

        - 高级用户 → context_id = user_id (固定)
        - 普通用户 → context_id = chat_key (等同对话窗口)
        """
        is_advanced = self._is_advanced_sender(user_id)
        context_id = user_id if is_advanced else chat_key

        # 内存缓存命中
        if context_id in self._windows:
            return self._windows[context_id]

        # 从 DB 加载或创建
        window = await DBContextWindow.get_or_none(context_id=context_id)
        if not window:
            window = await DBContextWindow.create(
                context_id=context_id,
                owner_type="advanced" if is_advanced else "normal",
                active_dialog_id=chat_key,
                permission_level="advanced" if is_advanced else "normal",
            )
            logger.info(f"创建上下文窗口: {context_id} (type={window.owner_type})")

        self._windows[context_id] = window
        return window

    # ── 锚定管理 ──

    async def update_anchor(
        self,
        context_id: str,
        dialog_chat_key: str,
    ) -> None:
        """更新上下文窗口的锚定对话窗口（回复目标）

        tool 链执行期间锁定锚定，不允许切换。
        """
        window = self._windows.get(context_id)
        if not window:
            window = await DBContextWindow.get_or_none(context_id=context_id)
            if not window:
                logger.warning(f"update_anchor: 上下文窗口不存在 {context_id}")
                return
            self._windows[context_id] = window

        # tool 链执行期间锁定锚定
        if window.tool_chain_active:
            logger.debug(
                f"上下文窗口 {context_id} tool 链运行中，锚定锁定在 {window.active_dialog_id}，"
                f"忽略切换请求 → {dialog_chat_key}"
            )
            return

        if window.active_dialog_id != dialog_chat_key:
            old = window.active_dialog_id
            window.active_dialog_id = dialog_chat_key
            await window.save(update_fields=["active_dialog_id", "updated_at"])
            logger.info(f"上下文窗口 {context_id} 锚定切换: {old} → {dialog_chat_key}")

    # ── 消息注入 ──

    async def inject_messages(
        self,
        context_id: str,
        messages: List[Dict[str, Any]],
        max_inject: int = 8,
    ) -> int:
        """注入新消息到上下文窗口历史

        Args:
            context_id: 上下文窗口 ID
            messages: 待注入的消息列表，每条包含:
                - sender_id, sender_name, content_text, images[], role等
            max_inject: 群聊防爆上限（默认 8 条）

        Returns:
            实际注入的消息数量

        注意：
        - 8 条限制只计算 human_chat 类型（人类发的消息）
        - tool_call / tool_result / bot_reply 不计入防爆
        - 已注入过的消息不重复注入
        """
        injected_count = 0
        human_count = 0
        auto_memory_count = 0
        latest_context_msg_id = 0
        latest_source_chat_key = ""

        for msg in messages:
            msg_id = msg.get("source_message_id", "")
            msg_type = msg.get("msg_type", "human_chat")
            role = msg.get("role", "user")

            # DB 去重：检查是否已存在相同 source_message_id
            if msg_id:
                exists = await DBContextMessage.filter(
                    context_id=context_id,
                    source_message_id=msg_id,
                ).exists()
                if exists:
                    continue

            # 防爆：只限制 human_chat
            if msg_type == "human_chat":
                if human_count >= max_inject:
                    continue
                human_count += 1

            # 序列化 parts
            parts = msg.get("parts", [])
            serialized_parts = []
            for part in parts:
                part_dict = self._part_to_dict(part)
                if part_dict.get("type") == "text" and isinstance(part_dict.get("text"), str):
                    if self._should_sanitize_bot_assistant_text(role, msg_type):
                        part_dict["text"] = self._sanitize_bot_assistant_text(part_dict["text"])
                    else:
                        part_dict["text"] = self._sanitize_text(part_dict["text"])
                    if not part_dict["text"]:
                        continue
                serialized_parts.append(part_dict)
            parts_json = json.dumps(
                serialized_parts,
                ensure_ascii=False,
            )

            # tool_calls 序列化
            tool_calls = msg.get("tool_calls")
            tool_calls_json = ""
            if tool_calls:
                serialized_tool_calls = []
                for tc in tool_calls:
                    item = {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    meta = dict(getattr(tc, "meta", {}) or {})
                    if meta:
                        item["_hcz_meta"] = meta
                    serialized_tool_calls.append(item)
                tool_calls_json = json.dumps(serialized_tool_calls, ensure_ascii=False)

            created = await DBContextMessage.create(
                context_id=context_id,
                role=role,
                sender_id=msg.get("sender_id", ""),
                sender_name=msg.get("sender_name", ""),
                parts_json=parts_json,
                tool_call_id=msg.get("tool_call_id", ""),
                tool_calls_json=tool_calls_json,
                source_chat_key=msg.get("source_chat_key", ""),
                source_message_id=msg_id,
                msg_type=msg_type,
            )

            latest_context_msg_id = int(getattr(created, "id", 0) or latest_context_msg_id)
            latest_source_chat_key = str(msg.get("source_chat_key", "") or latest_source_chat_key)
            if msg_type in {"human_chat"} and str(msg.get("role", "user")) in {"user", "assistant"}:
                auto_memory_count += 1
            injected_count += 1

        # 更新消息计数
        window = self._windows.get(context_id)
        if window:
            window.msg_count_since_compress += injected_count
            await window.save(update_fields=["msg_count_since_compress", "updated_at"])

        await self.enforce_history_hard_limit(context_id)

        if auto_memory_count > 0 and latest_context_msg_id > 0:
            try:
                from holo_cortex_zero.services.memory import auto_memory_service
                await auto_memory_service.record_context_messages(
                    context_id=context_id,
                    latest_context_msg_id=latest_context_msg_id,
                    message_count=auto_memory_count,
                    dialog_chat_key=latest_source_chat_key,
                )
            except Exception as e:
                logger.error(f"auto_memory 注入计数更新失败: ctx={context_id}: {e}", exc_info=True)

        return injected_count

    # ── 历史获取 ──

    async def get_history(
        self,
        context_id: str,
        limit: Optional[int] = None,
    ) -> List[MessageTurn]:
        """获取上下文窗口的 IR 格式历史

        默认返回最近 max_history * 1.2 条（120条，20%冗余给 timeline 生成窗口）。
        超出的旧消息会被截断（timeline 集成后由压缩管理）。
        """
        if limit is not None:
            effective_limit = limit
        elif await self._is_normal_context(context_id):
            effective_limit = self._get_normal_context_reset_threshold()
        else:
            effective_limit = int(self.max_history_before_compress * self.hard_limit_ratio)

        # 先取总数，如果超限则只取最新的
        total = await DBContextMessage.filter(context_id=context_id).count()
        query = DBContextMessage.filter(context_id=context_id).order_by("id")
        if total > effective_limit:
            # 只取最新的 effective_limit 条
            query = DBContextMessage.filter(context_id=context_id).order_by("-id").limit(effective_limit)
            db_messages = await query.all()
            db_messages.reverse()  # 恢复时间顺序
            logger.debug(f"历史截断: {context_id} 总{total}条，只取最新{effective_limit}条")
        else:
            db_messages = await query.all()

        window = await self._get_window(context_id)
        active_dialog_id = str(getattr(window, "active_dialog_id", "") or "").strip()
        owner_type = str(getattr(window, "owner_type", "") or "").strip()
        active_dialog_is_group = self._is_group_chat_key(active_dialog_id)
        notice_policy = "keep_latest_in_active_group" if active_dialog_is_group else "drop_all_for_private"
        keep_notice_context_msg_id = 0

        if active_dialog_is_group:
            for candidate in reversed(db_messages):
                if str(candidate.msg_type or "") != "human_chat":
                    continue
                if str(getattr(candidate, "source_chat_key", "") or "").strip() != active_dialog_id:
                    continue
                if owner_type == "advanced" and str(candidate.role or "") != "user":
                    continue

                candidate_parts = self._parse_parts_json(candidate.parts_json)
                if not self._parts_have_group_trigger_notice(candidate_parts):
                    continue

                keep_notice_context_msg_id = int(getattr(candidate, "id", 0) or 0)
                break

        logger.debug(
            "主对话历史@裁剪判定: ctx=%s active_dialog=%s policy=%s owner_type=%s keep_ctx_msg_id=%s",
            context_id,
            active_dialog_id,
            notice_policy,
            owner_type,
            keep_notice_context_msg_id,
        )

        turns: List[MessageTurn] = []
        pending_tool_call_ids = deque[str]()
        stripped_group_notice_count = 0

        for db_msg in db_messages:
            if db_msg.msg_type == "history_only":
                continue

            parts = self._parse_parts_json(db_msg.parts_json)
            parts = self._sanitize_bot_assistant_parts(
                parts,
                role=db_msg.role,
                msg_type=db_msg.msg_type,
            )
            if str(db_msg.msg_type or "") == "human_chat":
                keep_notice = bool(
                    active_dialog_is_group
                    and keep_notice_context_msg_id
                    and int(getattr(db_msg, "id", 0) or 0) == keep_notice_context_msg_id
                )
                parts, stripped_count = self._normalize_history_group_trigger_notice_parts(
                    parts,
                    keep_notice=keep_notice,
                )
                stripped_group_notice_count += stripped_count
            if str(db_msg.msg_type or "") == "system_inject":
                parts = self._apply_notice_prefix_to_parts(parts, "系统通知。")
            tool_calls = self._parse_tool_calls_json(db_msg.tool_calls_json)
            tool_call_id = db_msg.tool_call_id or None

            if not parts and not tool_calls and not tool_call_id:
                logger.debug(
                    f"上下文空消息已跳过: ctx={context_id} db_msg={db_msg.id} msg_type={db_msg.msg_type}"
                )
                continue

            for tool_call in tool_calls:
                if tool_call.id:
                    pending_tool_call_ids.append(str(tool_call.id))

            if db_msg.role == "tool":
                if tool_call_id:
                    try:
                        pending_tool_call_ids.remove(str(tool_call_id))
                    except ValueError:
                        pass
                elif pending_tool_call_ids:
                    tool_call_id = pending_tool_call_ids.popleft()
                    logger.info(
                        f"上下文历史顺序回填 tool_call_id: ctx={context_id} db_msg={db_msg.id} call_id={tool_call_id}"
                    )

            turn = MessageTurn(
                role=db_msg.role,  # type: ignore[arg-type]
                parts=parts,
                name=db_msg.sender_name or None,
                tool_call_id=tool_call_id,
                tool_calls=tool_calls if tool_calls else None,
                reasoning_content=self._parse_reasoning_content_from_tool_calls_json(db_msg.tool_calls_json),
            )
            turns.append(turn)

        if stripped_group_notice_count:
            logger.info(
                "主对话历史@裁剪已生效: ctx=%s active_dialog=%s policy=%s stripped=%s keep_ctx_msg_id=%s",
                context_id,
                active_dialog_id,
                notice_policy,
                stripped_group_notice_count,
                keep_notice_context_msg_id,
            )

        return turns

    # ── Timeline 压缩管理 ──

    async def check_and_trigger_compress(
        self,
        context_id: str,
    ) -> bool:
        """检查是否需要触发 timeline 压缩

        盯的是 DBContextMessage 的实际条数（上下文窗口历史），不是对话窗口消息数。
        触发后交给内置 timeline_service 后台执行，不阻塞当前请求。
        """
        if await self._is_normal_context(context_id):
            logger.info("普通 context 已改走归档式回收，不触发旧 timeline: ctx=%s", context_id)
            return False

        # 直接查 DB 实际条数，不依赖内存计数器
        actual_count = await DBContextMessage.filter(context_id=context_id).count()

        from holo_cortex_zero.services.context_window.timeline import timeline_service
        return await timeline_service.maybe_trigger(
            context_id, actual_count, self.max_history_before_compress,
        )

    async def set_pending_summary(
        self,
        context_id: str,
        summary: str,
    ) -> None:
        """timeline 生成完成后调用：设置待应用的摘要"""
        window = self._windows.get(context_id)
        if not window:
            window = await DBContextWindow.get_or_none(context_id=context_id)
            if not window:
                return
            self._windows[context_id] = window

        sanitized_summary = self.sanitize_model_output_text(summary)
        if sanitized_summary != summary:
            logger.info(f"上下文窗口 {context_id} 的 pending_summary 已清洗脏文本")

        window.pending_summary = sanitized_summary
        window.pending_summary_ready = True
        window.summary_generating = False
        await window.save(update_fields=["pending_summary", "pending_summary_ready", "summary_generating", "updated_at"])
        logger.info(f"上下文窗口 {context_id} 新摘要已生成并标记 ready")

    async def try_apply_ready_summary(
        self,
        context_id: str,
    ) -> bool:
        """检查是否有已 ready 的新摘要，如果有则替换并清理历史

        调用时机：每次请求的上下文组装前。
        关键约束：只有新摘要 ready 后才清理历史！
        """
        window = self._windows.get(context_id)
        if not window:
            return False

        if str(window.owner_type or "") == "normal":
            if window.pending_summary_ready or window.summary_generating or window.pending_summary:
                window.pending_summary = ""
                window.pending_summary_ready = False
                window.summary_generating = False
                await window.save(update_fields=["pending_summary", "pending_summary_ready", "summary_generating", "updated_at"])
                logger.info("普通 context 已清理旧 timeline pending 状态: ctx=%s", context_id)
            logger.info("普通 context 已固定走归档式回收，不应用旧 timeline 摘要: ctx=%s", context_id)
            return False

        if not window.pending_summary_ready:
            return False

        new_summary = self.sanitize_model_output_text(window.pending_summary or "")
        if not new_summary.strip():
            # 摘要为空，不应用
            window.pending_summary_ready = False
            window.summary_generating = False
            await window.save(update_fields=["pending_summary_ready", "summary_generating", "updated_at"])
            return False

        # 1. 替换压缩摘要
        window.compressed_summary = new_summary
        window.last_compress_version += 1

        # 2. 清理历史到只保留最新 keep_recent 条
        total = await DBContextMessage.filter(context_id=context_id).count()
        if total > self.keep_recent_after_compress:
            # 删除最旧的消息，只保留最新的 keep_recent 条
            keep_ids = (
                await DBContextMessage.filter(context_id=context_id)
                .order_by("-id")
                .limit(self.keep_recent_after_compress)
                .values_list("id", flat=True)
            )
            await DBContextMessage.filter(
                context_id=context_id
            ).exclude(id__in=keep_ids).delete()

            logger.info(
                f"上下文窗口 {context_id} 压缩清理: {total} → {self.keep_recent_after_compress} 条"
            )

        # 3. 重置计数器和 pending 标记
        window.msg_count_since_compress = 0
        window.pending_summary = ""
        window.pending_summary_ready = False
        window.summary_generating = False
        await window.save(
            update_fields=[
                "compressed_summary",
                "last_compress_version",
                "msg_count_since_compress",
                "pending_summary",
                "pending_summary_ready",
                "summary_generating",
                "updated_at",
            ]
        )

        logger.info(f"上下文窗口 {context_id} 摘要已应用 (v{window.last_compress_version})")
        return True

    # ── Tool 链状态管理 ──

    async def start_tool_chain(self, context_id: str) -> None:
        """标记 tool 链开始"""
        window = self._windows.get(context_id)
        if window:
            window.tool_chain_active = True
            window.tool_chain_iteration = 0
            await window.save(update_fields=["tool_chain_active", "tool_chain_iteration", "updated_at"])

    async def end_tool_chain(self, context_id: str) -> None:
        """标记 tool 链结束"""
        window = self._windows.get(context_id)
        if window:
            window.tool_chain_active = False
            window.tool_chain_iteration = 0
            await window.save(update_fields=["tool_chain_active", "tool_chain_iteration", "updated_at"])

    async def increment_tool_chain(self, context_id: str) -> int:
        """tool 链迭代 +1，返回当前迭代次数"""
        window = self._windows.get(context_id)
        if window:
            window.tool_chain_iteration += 1
            await window.save(update_fields=["tool_chain_iteration", "updated_at"])
            return window.tool_chain_iteration
        return 0

    def is_tool_chain_active(self, context_id: str) -> bool:
        """检查 tool 链是否正在运行"""
        window = self._windows.get(context_id)
        return bool(window and window.tool_chain_active)

    # ── 重启恢复 ──

    async def on_restart_recover(self) -> None:
        """重启恢复：从 DB 重建所有活跃窗口的内存态 + 强清理脏数据"""
        windows = await DBContextWindow.all()
        for w in windows:
            self._windows[w.context_id] = w
            # 清理重启前遗留的 tool 链状态
            if w.tool_chain_active:
                w.tool_chain_active = False
                w.tool_chain_iteration = 0
                await w.save(update_fields=["tool_chain_active", "tool_chain_iteration", "updated_at"])
                logger.info(f"重启恢复: 清理上下文窗口 {w.context_id} 的遗留 tool 链状态")
            if w.summary_generating and not w.pending_summary_ready:
                w.summary_generating = False
                await w.save(update_fields=["summary_generating", "updated_at"])
                logger.warning(f"重启恢复: 清理上下文窗口 {w.context_id} 的遗留 timeline 生成锁")

        logger.info(f"重启恢复: 加载了 {len(windows)} 个上下文窗口")

        # 强清理脏数据（prompt 防御）
        await self._purge_dirty_context_messages()

    async def _purge_dirty_context_messages(self) -> None:
        """强清理 context_message 表中的脏数据

        删除条件：
        1. parts_json 包含 [数字|名字] 格式（旧 ID 前缀污染）
        2. parts_json 包含 <tool_call> 标签（旧 tool 输出残留）
        3. parts_json 包含 <function= 标签（Qwen 原生 tool 输出残留）
        """
        from tortoise.expressions import Q

        dirty_count = 0

        # 查出所有可能脏的记录
        # 用 contains 查询比全表扫描高效
        dirty_patterns = [
            Q(parts_json__contains="[1917408441|"),  # 具体 ID 格式
            Q(parts_json__contains="【工具调用】"),
            Q(parts_json__contains="<tool_call>"),
            Q(parts_json__contains="<function="),
            Q(parts_json__contains="发送聊天消息文本"),
        ]

        for pattern in dirty_patterns:
            count = await DBContextMessage.filter(pattern).delete()
            dirty_count += count

        # 通用 [数字|名字] 格式清理：先查再删（正则不能在 SQL 中用）
        all_msgs = await DBContextMessage.filter(
            parts_json__contains="|"
        ).all()
        ids_to_delete = []
        for msg in all_msgs:
            if self._ID_NAME_PATTERN.search(msg.parts_json):
                ids_to_delete.append(msg.id)

        if ids_to_delete:
            await DBContextMessage.filter(id__in=ids_to_delete).delete()
            dirty_count += len(ids_to_delete)

        if dirty_count > 0:
            logger.info(f"强清理: 删除了 {dirty_count} 条脏 context_message 记录")

    # ── 辅助方法 ──

    @staticmethod
    def _part_to_dict(part: MessagePart) -> Dict[str, Any]:
        """MessagePart → dict（for JSON serialization）"""
        data: Dict[str, Any] = {"type": part.type}
        if part.text is not None:
            data["text"] = part.text
        if part.url is not None:
            data["url"] = part.url
        if part.mime_type is not None:
            data["mime_type"] = part.mime_type
        if part.detail != "auto":
            data["detail"] = part.detail
        return data

    # 脏数据正则（实时清洗，每次读取历史都执行）
    _DIRTY_TOOL_CALL = re.compile(r'<tool_call>.*?</tool_call>', re.DOTALL)
    _DIRTY_FUNCTION = re.compile(r'<function=[^>]*>.*?</function>', re.DOTALL)
    _DIRTY_TOOL_CALL_TEXT = re.compile(r'(^|\n)【工具调用】[^\n]*', re.MULTILINE)
    _BOT_TRANSPORT_FILE_PROMPT = re.compile(r'\[File: /[^\]]+\]')
    _BOT_HISTORY_MEDIA_PLACEHOLDER = re.compile(r'\[bot历史(?:图片文件|图片): [^\]]+\]')
    _THINK_TAG_TOKEN = re.compile(r'<\s*(/?)\s*think\s*>', re.IGNORECASE)
    _BOT_ASSISTANT_MSG_TYPES = {"bot_reply", "bot_sync", "tool_call", "history_only"}

    @staticmethod
    def _strip_think_artifacts(text: str) -> str:
        """强兜底清洗 think 标签及其污染内容。"""
        if not text or 'think' not in text.lower():
            return text

        result: List[str] = []
        cursor = 0
        depth = 0

        for match in ContextWindowManager._THINK_TAG_TOKEN.finditer(text):
            is_close = bool(match.group(1))

            if depth == 0:
                if is_close:
                    result = []
                    cursor = match.end()
                    continue

                result.append(text[cursor:match.start()])
                depth = 1
                cursor = match.end()
                continue

            if is_close:
                depth -= 1
            else:
                depth += 1
            cursor = match.end()

        if depth == 0:
            result.append(text[cursor:])

        cleaned = ''.join(result)
        cleaned = ContextWindowManager._THINK_TAG_TOKEN.sub('', cleaned)
        return cleaned

    @staticmethod
    def sanitize_model_output_text(text: str) -> str:
        """强兜底清洗模型输出，防止思维链进入用户侧或上下文。"""
        return ContextWindowManager._sanitize_text(text)

    @staticmethod
    def _should_sanitize_bot_assistant_text(role: Any, msg_type: Any) -> bool:
        return (
            str(role or "").strip() == "assistant"
            and str(msg_type or "").strip() in ContextWindowManager._BOT_ASSISTANT_MSG_TYPES
        )

    @staticmethod
    def _sanitize_bot_assistant_text(text: str) -> str:
        """清洗真实 bot/model assistant 文本，不触碰用户原话或 tool/system 文本。"""
        cleaned = ContextWindowManager._sanitize_text(str(text or ""))
        return normalize_bot_surface_text(cleaned)

    @staticmethod
    def _sanitize_bot_assistant_parts(
        parts: List[MessagePart],
        *,
        role: Any,
        msg_type: Any,
    ) -> List[MessagePart]:
        if not ContextWindowManager._should_sanitize_bot_assistant_text(role, msg_type):
            return parts

        sanitized_parts: List[MessagePart] = []
        for part in parts:
            if part.type == "text" and isinstance(part.text, str):
                clean_text = ContextWindowManager._sanitize_bot_assistant_text(part.text)
                if not clean_text:
                    continue
                part.text = clean_text
            sanitized_parts.append(part)
        return sanitized_parts

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """实时清洗文本中的所有脏格式（prompt 防御层）

        每次从 DB 读取历史时都执行，不依赖重启。
        """
        if not text:
            return text
        text = ContextWindowManager._strip_think_artifacts(text)
        text = ContextWindowManager._ID_NAME_PATTERN.sub('', text)
        text = ContextWindowManager._DIRTY_TOOL_CALL.sub('', text)
        text = ContextWindowManager._DIRTY_FUNCTION.sub('', text)
        text = ContextWindowManager._DIRTY_TOOL_CALL_TEXT.sub('\n', text)
        text = ContextWindowManager._BOT_TRANSPORT_FILE_PROMPT.sub('', text)
        text = ContextWindowManager._BOT_HISTORY_MEDIA_PLACEHOLDER.sub('', text)
        text = ContextWindowManager._THINK_TAG_TOKEN.sub('', text)
        return text.strip()

    @staticmethod
    def _parse_parts_json(parts_json: str) -> List[MessagePart]:
        """JSON → List[MessagePart]，实时清洗脏数据"""
        if not parts_json or parts_json == "[]":
            return []
        try:
            items = json.loads(parts_json)
        except json.JSONDecodeError:
            return []
        parts: List[MessagePart] = []
        for item in items:
            text = item.get("text")
            if text and isinstance(text, str):
                text = ContextWindowManager._sanitize_text(text) or None
            part_type = item.get("type", "text")
            if text is None and part_type == "text":
                continue  # 清洗后为空的纯文本 part 丢弃

            data_b64 = item.get("data_b64")
            data: Optional[bytes] = None
            if isinstance(data_b64, str) and data_b64:
                try:
                    data = base64.b64decode(data_b64.encode("ascii"), validate=True)
                except (ValueError, binascii.Error) as exc:
                    logger.warning(f"上下文媒体 data_b64 解码失败，降级忽略二进制: {exc}")
                    data = None

            url = item.get("url")
            mime_type = item.get("mime_type")
            if part_type == "image" and not url and data is None:
                parts.append(MessagePart(type="text", text="[历史图片]"))
                continue

            parts.append(MessagePart(
                type=part_type,
                text=text,
                url=url,
                data=data,
                mime_type=mime_type,
                detail=item.get("detail", "auto"),
                meta=item.get("meta") if isinstance(item.get("meta"), dict) else {},
            ))
        return parts

    @staticmethod
    def _parse_tool_calls_json(tc_json: Optional[str]) -> List[ToolCall]:
        """JSON → List[ToolCall]"""
        if not tc_json:
            return []
        try:
            items = json.loads(tc_json)
        except json.JSONDecodeError:
            return []
        tool_calls: List[ToolCall] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tool_call_id = str(item.get("id") or "").strip()
            tool_name = str(item.get("name") or "").strip()
            if not tool_call_id and not tool_name:
                continue
            meta = dict(item.get("_hcz_meta") or {}) if isinstance(item.get("_hcz_meta"), dict) else {}
            meta.pop("reasoning_content", None)
            tool_calls.append(ToolCall(
                id=tool_call_id,
                name=tool_name,
                arguments=item.get("arguments", {}),
                meta=meta,
            ))
        return tool_calls

    @staticmethod
    def _parse_reasoning_content_from_tool_calls_json(tc_json: Optional[str]) -> Optional[str]:
        if not tc_json:
            return None
        try:
            items = json.loads(tc_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(items, list) or not items:
            return None
        first = items[0]
        if not isinstance(first, dict):
            return None
        meta = first.get("_hcz_meta")
        if not isinstance(meta, dict):
            return None
        value = meta.get("reasoning_content")
        if not isinstance(value, str) or not value.strip():
            return None
        return value

    async def sync_new_chat_messages(
        self,
        context_id: str,
        dialog_chat_key: str,
        max_inject: int = 8,
    ) -> int:
        """从对话窗口拉取最新未注入的聊天消息

        极简逻辑：
        1. 只看当前 dialog_chat_key 过去 12 小时内的新消息
        2. 候选必须是“未读过”的 chat_message（source_message_id 去重）
        3. 人类消息最多注入 max_inject 条，bot 消息同步但不占人类名额
        4. 不回填更老 backlog，不分批补历史
        """
        from holo_cortex_zero.models.db_chat_message import DBChatMessage

        cutoff_ts = int(time.time()) - 12 * 60 * 60

        # 1. 当前窗口内已注入的 source_message_id 集合（DB 查询，重启安全）
        already_injected = set(
            await DBContextMessage.filter(
                context_id=context_id,
                source_chat_key=dialog_chat_key,
            ).values_list("source_message_id", flat=True)
        )
        already_injected_base = {
            self._normalize_source_message_id(source_id)
            for source_id in already_injected
            if str(source_id or "").strip()
        }

        # 2. 当前窗口已同步到的最新 DBChatMessage.id
        last_synced_db_id = await self._get_dialog_last_synced_db_id(context_id, dialog_chat_key)

        # 3. 只取 12 小时内、比上次已读更新的消息；不返不分批
        collected: List[Dict[str, Any]] = []
        human_count = 0
        bot_count = 0
        candidates = await DBChatMessage.filter(
            chat_key=dialog_chat_key,
            id__gt=last_synced_db_id,
            send_timestamp__gte=cutoff_ts,
        ).order_by("-id").all()
        latest_seen_db_id = int(candidates[0].id) if candidates else last_synced_db_id

        for db_msg in candidates:
            is_system_msg = self._is_system_db_msg(db_msg)
            if is_system_msg:
                continue

            sanitized_sender_name = self._sanitize_sender_name_for_context(
                self._resolve_sender_id(db_msg),
                db_msg.sender_nickname or db_msg.sender_name or "",
            )

            msg_id = str(db_msg.message_id or "")
            dedup_key = msg_id if msg_id else f"dbid_{db_msg.id}"
            if dedup_key in already_injected_base:
                continue

            is_bot = str(db_msg.sender_id).strip() == "-1" and not is_system_msg
            if is_bot:
                parts = self._db_msg_to_parts_bot(db_msg)
                if not parts:
                    continue
                bot_count += 1
                collected.append({
                    "role": "assistant",
                    "sender_id": db_msg.sender_id,
                    "sender_name": sanitized_sender_name,
                    "parts": parts,
                    "source_chat_key": dialog_chat_key,
                    "source_message_id": dedup_key,
                    "msg_type": "bot_sync",
                })
                continue

            if human_count >= max_inject:
                break
            human_count += 1

            append_sender_attribution = self._should_append_sender_attribution(
                context_id=context_id,
                dialog_chat_key=dialog_chat_key,
                db_msg=db_msg,
            )
            parts = self._db_msg_to_parts(
                db_msg,
                append_sender_attribution=append_sender_attribution,
            )
            role = self._determine_role_for_db_msg(db_msg, context_id)
            has_image_segment = self._db_msg_has_image_segment(db_msg)

            if role == "assistant" and has_image_segment:
                collected.append({
                    "role": "user",
                    "sender_id": db_msg.sender_id,
                    "sender_name": sanitized_sender_name,
                    "parts": self._build_user_image_parts(db_msg, parts),
                    "source_chat_key": dialog_chat_key,
                    "source_message_id": dedup_key,
                    "msg_type": "human_chat",
                })
                continue

            if role == "assistant":
                text_parts = [part for part in parts if part.type not in {"image", "audio", "video"}]
                media_parts = [part for part in parts if part.type in {"image", "audio", "video"}]

                if text_parts:
                    collected.append({
                        "role": "assistant",
                        "sender_id": db_msg.sender_id,
                        "sender_name": sanitized_sender_name,
                        "parts": text_parts,
                        "source_chat_key": dialog_chat_key,
                        "source_message_id": f"{dedup_key}#text",
                        "msg_type": "human_chat",
                    })

                if media_parts:
                    media_message_parts = media_parts
                    collected.append({
                        "role": "user",
                        "sender_id": db_msg.sender_id,
                        "sender_name": sanitized_sender_name,
                        "parts": media_message_parts,
                        "source_chat_key": dialog_chat_key,
                        "source_message_id": f"{dedup_key}#media",
                        "msg_type": "human_chat",
                    })
                elif not text_parts:
                    collected.append({
                        "role": "assistant",
                        "sender_id": db_msg.sender_id,
                        "sender_name": sanitized_sender_name,
                        "parts": parts,
                        "source_chat_key": dialog_chat_key,
                        "source_message_id": dedup_key,
                        "msg_type": "human_chat",
                    })
                continue

            collected.append({
                "role": role,
                "sender_id": db_msg.sender_id,
                "sender_name": sanitized_sender_name,
                "parts": parts,
                "source_chat_key": dialog_chat_key,
                "source_message_id": dedup_key,
                "msg_type": "human_chat",
            })

        # 4. 按时间正序（反转，因为收集时是从新到旧）
        collected.reverse()

        if collected:
            injected_count = await self.inject_messages(context_id, collected, max_inject=999)
            await self._set_dialog_last_synced_db_id(
                context_id=context_id,
                dialog_chat_key=dialog_chat_key,
                last_synced_db_id=latest_seen_db_id,
            )
            logger.info(
                f"sync {dialog_chat_key} → {context_id}: "
                f"since_db_id={last_synced_db_id} human={human_count} bot={bot_count} "
                f"window=12h"
            )
            return injected_count

        if latest_seen_db_id > last_synced_db_id:
            await self._set_dialog_last_synced_db_id(
                context_id=context_id,
                dialog_chat_key=dialog_chat_key,
                last_synced_db_id=latest_seen_db_id,
            )
        return 0

    def _db_msg_to_parts(self, db_msg: Any, *, append_sender_attribution: bool = False) -> List[MessagePart]:
        """将 DBChatMessage 转为 MessagePart 列表

        发送者标识用 ¥ 包围的系统运行状态符格式：¥昵称¥日期时间¥ID¥说：
        ¥ 格式在 system prompt 中明确声明为系统标记，禁止 bot 模仿。
        """
        parts: List[MessagePart] = []
        prefix = self._build_db_msg_prefix(db_msg)
        sender_id = self._resolve_sender_id(db_msg)
        sender_name = self._resolve_sender_name(db_msg, sender_id)
        attribution_suffix = (
            self._build_sender_attribution_suffix(sender_id=sender_id, sender_name=sender_name)
            if append_sender_attribution
            else ""
        )
        context_notice_prefix = self._extract_db_msg_context_notice_prefix(db_msg)
        segments: List[Any] = []
        reference_parts_count = 0
        notice_inserted = False

        # 解析图片等多模态内容
        try:
            segments = db_msg.parse_content_data()
            from holo_cortex_zero.schemas.chat_message import (
                ChatMessageSegmentFile,
                ChatMessageSegmentImage,
                ChatMessageSegmentReference,
            )
            for seg in segments:
                if isinstance(seg, ChatMessageSegmentReference):
                    parts.extend(self._reference_segment_to_parts(db_msg, seg))
            reference_parts_count = len(parts)

            if db_msg.content_text:
                clean_text = self._sanitize_text(db_msg.content_text).strip()
                if clean_text:
                    merged_text = self._merge_notice_prefix(context_notice_prefix, clean_text)
                    body_text = f"{merged_text}{attribution_suffix}"
                    parts.append(MessagePart(type="text", text=prefix + body_text if prefix else body_text))
                    notice_inserted = bool(context_notice_prefix)

            for seg in segments:
                if isinstance(seg, ChatMessageSegmentReference):
                    continue
                if isinstance(seg, ChatMessageSegmentImage):
                    parts.extend(
                        self._db_image_segment_to_parts(
                            db_msg,
                            seg,
                            append_sender_attribution=append_sender_attribution,
                        )
                    )
                elif isinstance(seg, ChatMessageSegmentFile):
                    parts.extend(
                        self._db_file_segment_to_parts(
                            db_msg,
                            seg,
                            append_sender_attribution=append_sender_attribution,
                        )
                    )
        except Exception as e:
            logger.debug(f"解析消息多模态内容失败: {e}")

        if context_notice_prefix and not notice_inserted:
            notice_body = f"{context_notice_prefix}{attribution_suffix}"
            notice_text = prefix + notice_body if prefix else notice_body
            parts.insert(reference_parts_count, MessagePart(type="text", text=notice_text))
            notice_inserted = True

        if not parts and db_msg.content_text:
            clean_text = self._sanitize_text(db_msg.content_text).strip()
            if clean_text:
                merged_text = self._merge_notice_prefix(context_notice_prefix, clean_text)
                body_text = f"{merged_text}{attribution_suffix}"
                parts.append(MessagePart(type="text", text=prefix + body_text if prefix else body_text))

        has_only_empty_at = False
        try:
            from holo_cortex_zero.schemas.chat_message import ChatMessageSegmentAt

            has_only_empty_at = bool(segments) and all(isinstance(seg, ChatMessageSegmentAt) for seg in segments)
        except Exception:
            has_only_empty_at = False

        if not parts and has_only_empty_at:
            logger.info(
                "上下文空@消息已跳过注入: chat=%s sender=%s msg_id=%s",
                getattr(db_msg, "chat_key", ""),
                getattr(db_msg, "platform_userid", "") or getattr(db_msg, "sender_id", ""),
                getattr(db_msg, "message_id", ""),
            )
            return []

        if not parts:
            body_text = f"[消息]{attribution_suffix}"
            parts.append(MessagePart(type="text", text=f"{prefix}{body_text}" if prefix else body_text))

        return parts

    @staticmethod
    def _resolve_runtime_local_path(path: Any) -> Optional[Path]:
        raw = str(path or "").strip()
        if not raw:
            return None

        candidate = Path(raw).expanduser()
        if candidate.exists():
            return candidate.resolve()

        if not candidate.is_absolute():
            return None

        workspace_root = Path(OsEnv.WORKSPACE_ROOT).resolve()
        candidate_parts = candidate.parts

        workspace_anchors = ("shared", "self_image", "emoji")
        for anchor in workspace_anchors:
            if anchor not in candidate_parts:
                continue
            anchor_index = candidate_parts.index(anchor)
            remapped = workspace_root.joinpath(*candidate_parts[anchor_index:])
            if remapped.exists():
                logger.info(
                    f"上下文媒体旧路径已重写到当前工作区: raw={candidate} remapped={remapped.resolve()}"
                )
                return remapped.resolve()

        data_root = Path(OsEnv.DATA_DIR).resolve()
        data_anchors = ("uploads", "quarantine_uploads", "tmp", "backups", "system", "napcat_data")
        for anchor in data_anchors:
            if anchor not in candidate_parts:
                continue
            anchor_index = candidate_parts.index(anchor)
            remapped = data_root.joinpath(*candidate_parts[anchor_index:])
            if remapped.exists():
                logger.info(
                    f"上下文媒体旧路径已重写到当前数据目录: raw={candidate} remapped={remapped.resolve()}"
                )
                return remapped.resolve()

        return None

    def _resolve_db_msg_image_path(self, db_msg: Any, seg: Any) -> Optional[str]:
        """解析聊天记录图片对应的宿主机路径。"""
        img_path = None
        if getattr(seg, "local_path", None):
            img_path = self._resolve_runtime_local_path(seg.local_path)
        elif getattr(seg, "file_name", None):
            img_path = self._resolve_runtime_local_path(Path(OsEnv.DATA_DIR) / "uploads" / db_msg.chat_key / seg.file_name)

        if not img_path:
            return None
        if quarantine_file_service.is_quarantine_path(img_path):
            expires_at = self._segment_expires_at(seg)
            if quarantine_file_service.remove_if_expired(img_path, expires_at=expires_at):
                return None
        if img_path.exists():
            return str(img_path)
        return None

    @staticmethod
    def _resolve_db_msg_remote_url(seg: Any) -> Optional[str]:
        remote_url = str(getattr(seg, "remote_url", None) or "").strip()
        if remote_url.startswith(("http://", "https://", "data:")):
            return remote_url
        return None

    def _resolve_db_msg_file_path(self, db_msg: Any, seg: Any) -> Optional[Path]:
        file_path: Optional[Path] = None
        if getattr(seg, "local_path", None):
            file_path = self._resolve_runtime_local_path(seg.local_path)
        elif getattr(seg, "file_name", None):
            file_path = self._resolve_runtime_local_path(Path(OsEnv.DATA_DIR) / "uploads" / db_msg.chat_key / seg.file_name)
        if file_path and file_path.exists():
            return file_path
        return None

    @staticmethod
    def _classify_db_msg_file(file_name: str, file_path: Optional[Path], mime_hint: Optional[str] = None) -> tuple[str, Optional[str]]:
        ext = Path(file_name or "").suffix.lower()
        mime_type = str(mime_hint or "").strip() or mimetypes.guess_type(str(file_path or file_name or ""))[0]
        audio_exts = {".mp3", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".flac", ".aac", ".amr", ".silk", ".webm"}
        video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

        if mime_type and mime_type.startswith("image/"):
            return "image", mime_type
        if mime_type and mime_type.startswith("audio/"):
            return "audio", mime_type
        if mime_type and mime_type.startswith("video/"):
            return "video", mime_type
        if ext in image_exts:
            return "image", mime_type or "image/jpeg"
        if ext in audio_exts:
            return "audio", mime_type or "audio/mpeg"
        if ext in video_exts:
            return "video", mime_type or "video/mp4"
        return "file", mime_type

    def _resolve_sender_id(self, db_msg: Any, sender_id_override: Optional[str] = None) -> str:
        if str(sender_id_override or "").strip():
            return str(sender_id_override).strip()
        return str(getattr(db_msg, "platform_userid", None) or getattr(db_msg, "sender_id", "") or "").strip()

    @staticmethod
    def _segment_expires_at(seg: Any) -> Optional[int]:
        raw = getattr(seg, "volatile_expires_at", None)
        try:
            return int(raw) if raw is not None else None
        except Exception:
            return None

    def _db_msg_has_image_segment(self, db_msg: Any) -> bool:
        try:
            from holo_cortex_zero.schemas.chat_message import ChatMessageSegmentImage

            segments = db_msg.parse_content_data()
            return any(isinstance(seg, ChatMessageSegmentImage) for seg in segments)
        except Exception as e:
            logger.debug(f"检测图片消息段失败: {e}")
            return False

    @staticmethod
    def _normalize_workspace_path(path: Any) -> str:
        raw = str(path or "").strip()
        if not raw:
            return ""
        try:
            candidate = Path(raw).resolve()
        except Exception:
            return ""

        try:
            workspace_root = Path(OsEnv.WORKSPACE_ROOT).resolve()
            if candidate == workspace_root:
                return "/workspace"
            if workspace_root in candidate.parents:
                return f"/workspace/{candidate.relative_to(workspace_root).as_posix()}"
        except Exception:
            pass

        try:
            emoji_root = (Path(OsEnv.DATA_DIR) / "system" / "emoji").resolve()
            if candidate == emoji_root:
                return "/workspace/emoji"
            if emoji_root in candidate.parents:
                return f"/workspace/emoji/{candidate.relative_to(emoji_root).as_posix()}"
        except Exception:
            pass

        return ""

    def _resolve_sender_name(self, db_msg: Any, sender_id: str) -> str:
        return self._sanitize_sender_name_for_context(
            sender_id,
            getattr(db_msg, "sender_nickname", None)
            or getattr(db_msg, "sender_name", None)
            or sender_id
            or "用户"
        ).strip() or "用户"

    def _build_sender_attribution_suffix(self, *, sender_id: str, sender_name: str) -> str:
        clean_name = self._sanitize_sender_name_for_context(
            sender_id,
            str(sender_name or sender_id or "用户").strip() or "用户",
        ).strip() or "用户"
        return f"**{clean_name}发的信息**"

    def _should_append_sender_attribution(self, *, context_id: str, dialog_chat_key: str, db_msg: Any) -> bool:
        if self._is_system_db_msg(db_msg):
            return False

        sender_id = self._resolve_sender_id(db_msg)
        if sender_id == "-1":
            return False

        is_advanced_context = self._is_advanced_sender(context_id)
        if not is_advanced_context:
            return True

        return self._is_group_chat_key(dialog_chat_key) and not self._is_advanced_sender(sender_id)

    @staticmethod
    def _media_label(part_type: str) -> str:
        return {
            "image": "图",
            "audio": "音频",
            "video": "视频",
            "file": "文件",
        }.get(str(part_type or "").strip().lower(), "文件")

    def _build_user_image_parts(self, db_msg: Any, parts: List[MessagePart]) -> List[MessagePart]:
        return list(parts or [])

    def _is_advanced_sender(self, sender_id: str) -> bool:
        return is_advanced_user_id(sender_id, config)

    def _build_media_notice(
        self,
        *,
        sender_id: str,
        sender_name: str,
        part_type: str,
        path: str = "",
        append_sender_attribution: bool = False,
    ) -> str:
        suffix = (
            self._build_sender_attribution_suffix(sender_id=sender_id, sender_name=sender_name)
            if append_sender_attribution
            else ""
        )
        public_path = self._normalize_workspace_path(path)
        if self._is_advanced_sender(sender_id):
            advanced_display_name = get_primary_advanced_user_display_name(config)
            if public_path:
                return f"{advanced_display_name}发送 {public_path}{suffix}"
            return f"{advanced_display_name}发送的{self._media_label(part_type)}{suffix}"

        clean_name = str(sender_name or sender_id or "用户").strip() or "用户"
        return f"{clean_name}发送的{self._media_label(part_type)}{suffix}"

    def _build_managed_path_notice(
        self,
        *,
        sender_id: str,
        sender_name: str,
        path: str,
        part_type: str,
        append_sender_attribution: bool = False,
    ) -> str:
        return self._build_media_notice(
            sender_id=sender_id,
            sender_name=sender_name,
            part_type=part_type,
            path=path,
            append_sender_attribution=append_sender_attribution,
        )


    def _db_image_segment_to_parts(
        self,
        db_msg: Any,
        seg: Any,
        *,
        sender_id_override: Optional[str] = None,
        sender_name_override: Optional[str] = None,
        append_sender_attribution: bool = False,
    ) -> List[MessagePart]:
        file_name = str(getattr(seg, "file_name", None) or "unknown")
        sender_id = self._resolve_sender_id(db_msg, sender_id_override)
        sender_name = (
            self._sanitize_sender_name_for_context(sender_id, sender_name_override)
            if str(sender_name_override or "").strip()
            else self._resolve_sender_name(db_msg, sender_id)
        )
        expires_at = self._segment_expires_at(seg)
        host_path = self._resolve_db_msg_image_path(db_msg, seg)
        if host_path:
            notice_text = self._build_managed_path_notice(
                sender_id=sender_id,
                sender_name=sender_name,
                path=host_path,
                part_type="image",
                append_sender_attribution=append_sender_attribution,
            )
            parts: List[MessagePart] = []
            if notice_text:
                parts.append(MessagePart(type="text", text=notice_text))
            parts.append(MessagePart(type="image", url=host_path, detail="auto"))
            source_kind = "quarantine" if quarantine_file_service.is_quarantine_path(host_path) else "local"
            logger.info(f"上下文图片来源: source={source_kind} file={file_name} path={host_path}")
            return parts
        if getattr(seg, "local_path", None) and expires_at and int(expires_at) <= int(time.time()):
            logger.info(f"上下文图片来源: source=quarantine_expired file={file_name} expires_at={expires_at}")
            return [
                MessagePart(
                    type="text",
                    text=self._build_media_notice(
                        sender_id=sender_id,
                        sender_name=sender_name,
                        part_type="image",
                        append_sender_attribution=append_sender_attribution,
                    ),
                )
            ]

        remote_url = self._resolve_db_msg_remote_url(seg)
        if remote_url:
            logger.info(f"上下文图片来源: source=remote file={file_name} url={remote_url[:128]}")
            return [
                MessagePart(
                    type="text",
                    text=self._build_media_notice(
                        sender_id=sender_id,
                        sender_name=sender_name,
                        part_type="image",
                        append_sender_attribution=append_sender_attribution,
                    ),
                ),
                MessagePart(type="image", url=remote_url, detail="auto"),
            ]

        logger.info(f"上下文图片来源: source=fallback_text file={file_name}")
        return [
            MessagePart(
                type="text",
                text=self._build_media_notice(
                    sender_id=sender_id,
                    sender_name=sender_name,
                    part_type="image",
                    append_sender_attribution=append_sender_attribution,
                ),
            )
        ]

    def _db_file_segment_to_parts(
        self,
        db_msg: Any,
        seg: Any,
        *,
        sender_id_override: Optional[str] = None,
        sender_name_override: Optional[str] = None,
        append_sender_attribution: bool = False,
    ) -> List[MessagePart]:
        file_name = str(getattr(seg, "file_name", None) or "unknown")
        sender_id = self._resolve_sender_id(db_msg, sender_id_override)
        sender_name = (
            self._sanitize_sender_name_for_context(sender_id, sender_name_override)
            if str(sender_name_override or "").strip()
            else self._resolve_sender_name(db_msg, sender_id)
        )
        file_path = self._resolve_db_msg_file_path(db_msg, seg)
        part_type, mime_type = self._classify_db_msg_file(
            file_name,
            file_path,
        )
        if part_type == "image":
            return self._db_image_segment_to_parts(
                db_msg,
                seg,
                sender_id_override=sender_id,
                sender_name_override=sender_name,
                append_sender_attribution=append_sender_attribution,
            )

        notice_text = self._build_managed_path_notice(
            sender_id=sender_id,
            sender_name=sender_name,
            path=str(file_path or ""),
            part_type=part_type,
            append_sender_attribution=append_sender_attribution,
        )
        parts: List[MessagePart] = []
        if notice_text:
            parts.append(MessagePart(type="text", text=notice_text))

        remote_url = self._resolve_db_msg_remote_url(seg)

        if part_type == "audio":
            if file_path:
                parts.append(MessagePart(type="audio", url=str(file_path), mime_type=mime_type))
                return parts
            if remote_url:
                parts.append(MessagePart(type="audio", url=remote_url, mime_type=mime_type))
                return parts
            return parts

        if part_type == "video":
            if file_path:
                parts.append(MessagePart(type="video", url=str(file_path), mime_type=mime_type))
                return parts
            if remote_url:
                parts.append(MessagePart(type="video", url=remote_url, mime_type=mime_type))
                return parts
            return parts

        if file_path:
            parts.append(MessagePart(type="file", url=str(file_path), mime_type=mime_type))
            return parts
        if remote_url:
            parts.append(MessagePart(type="file", url=remote_url, mime_type=mime_type))
            return parts
        return parts

    def _build_reference_header(self, seg: Any, *, label: str = "引用消息", include_text: bool = True) -> str:
        from holo_cortex_zero.schemas.chat_message import format_reference_timestamp

        ref_sender_id = str(getattr(seg, "ref_sender_id", None) or "").strip()
        sender_name = self._sanitize_sender_name_for_context(
            ref_sender_id,
            getattr(seg, "ref_sender_name", None) or ref_sender_id or "未知发送者",
        )
        timestamp_text = format_reference_timestamp(int(getattr(seg, "ref_send_timestamp", 0) or 0))
        header = f"【{label}｜{sender_name}｜{timestamp_text}】"
        ref_text = self._sanitize_text(str(getattr(seg, "ref_text", "") or "")).strip()
        return f"{header}{ref_text}" if include_text and ref_text else header

    def _reference_segment_to_parts(self, db_msg: Any, seg: Any) -> List[MessagePart]:
        parts: List[MessagePart] = [MessagePart(type="text", text=self._build_reference_header(seg))]
        if not bool(getattr(config, "REFERENCE_INCLUDE_MEDIA", True)):
            return parts

        try:
            ref_segments = seg.parse_ref_segments()
        except Exception as exc:
            logger.info(f"引用解析降级: state=fallback reason=parse_failed err={exc}")
            return parts

        from holo_cortex_zero.schemas.chat_message import ChatMessageSegmentFile, ChatMessageSegmentImage

        reference_sender_id = str(getattr(seg, "ref_sender_id", "") or "")
        reference_sender_name = self._sanitize_sender_name_for_context(
            reference_sender_id,
            getattr(seg, "ref_sender_name", None) or reference_sender_id or "未知发送者",
        )
        for ref_seg in ref_segments:
            if isinstance(ref_seg, ChatMessageSegmentImage):
                parts.extend(
                    self._db_image_segment_to_parts(
                        db_msg,
                        ref_seg,
                        sender_id_override=reference_sender_id,
                        sender_name_override=reference_sender_name,
                    ),
                )
            elif isinstance(ref_seg, ChatMessageSegmentFile):
                parts.extend(
                    self._db_file_segment_to_parts(
                        db_msg,
                        ref_seg,
                        sender_id_override=reference_sender_id,
                        sender_name_override=reference_sender_name,
                    ),
                )
        return parts

    def _build_reference_media_prefix(self, db_msg: Any) -> str:
        try:
            segments = db_msg.parse_content_data()
        except Exception:
            return ""
        from holo_cortex_zero.schemas.chat_message import (
            ChatMessageSegmentFile,
            ChatMessageSegmentImage,
            ChatMessageSegmentReference,
        )

        for seg in segments:
            if not isinstance(seg, ChatMessageSegmentReference):
                continue
            try:
                ref_segments = seg.parse_ref_segments()
            except Exception:
                ref_segments = []
            has_image = any(isinstance(item, ChatMessageSegmentImage) for item in ref_segments)
            has_media = has_image or any(isinstance(item, ChatMessageSegmentFile) for item in ref_segments)
            if has_image:
                return self._build_reference_header(seg, label="引用图片", include_text=False)
            if has_media:
                return self._build_reference_header(seg, label="引用媒体", include_text=False)
        return ""

    def _db_msg_to_parts_bot(self, db_msg: Any) -> List[MessagePart]:
        """将 bot 的 DBChatMessage 转为 MessagePart 列表

        与 _db_msg_to_parts 不同：不加 ¥ 前缀（bot 消息作为 assistant 角色，不需要发送者标识）。
        """
        parts: List[MessagePart] = []
        media_count = 0

        if db_msg.content_text:
            clean_text = self._sanitize_bot_assistant_text(db_msg.content_text).strip()
            if clean_text:
                parts.append(MessagePart(type="text", text=clean_text))

        # 图片等多模态内容
        try:
            segments = db_msg.parse_content_data()
            from holo_cortex_zero.schemas.chat_message import ChatMessageSegmentFile, ChatMessageSegmentImage
            for seg in segments:
                if isinstance(seg, ChatMessageSegmentImage):
                    media_count += 1
                elif isinstance(seg, ChatMessageSegmentFile):
                    media_count += 1
        except Exception as e:
            logger.debug(f"解析 bot 消息多模态内容失败: {e}")

        if media_count > 0:
            logger.debug(
                "bot 历史媒体段已跳过注入，避免附件重复进入上下文: "
                f"chat={getattr(db_msg, 'chat_key', '')} media_count={media_count}"
            )

        return parts

    def _determine_role_for_db_msg(self, db_msg: Any, context_id: str) -> str:
        """判断 DBChatMessage 在上下文中应该是什么角色

        主干规则（区分普通/高级上下文窗口）：
        - 系统消息 → user
        - 普通 context → 人类消息统一 user
        - 高级 context → 高级用户 user，其他人类 assistant

        注意：这里只决定“文本历史”的主角色，不改多模态 assistant→user
        兜底分流主干，避免为图片/音频/视频/文件再并一套特化逻辑。
        """
        if self._is_system_db_msg(db_msg):
            return "user"

        sender_id = str(db_msg.platform_userid or db_msg.sender_id).strip()
        normalized_context_id = str(context_id or "").strip()
        is_advanced_context = self._is_advanced_sender(normalized_context_id)

        if not is_advanced_context:
            logger.debug(
                "普通 context 历史消息按 user 注入: ctx=%s sender_id=%s",
                normalized_context_id,
                sender_id,
            )
            return "user"

        # 高级 context 中，只有高级用户 → user
        if self._is_advanced_sender(sender_id):
            return "user"

        logger.debug(
            "高级 context 非高级用户降级为 assistant: ctx=%s sender_id=%s",
            normalized_context_id,
            sender_id,
        )
        return "assistant"


# 全局单例
context_window_manager = ContextWindowManager()
