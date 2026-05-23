import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import magic

from holo_cortex_zero.adapters.interface.schemas.extra import PlatformMessageExt
from holo_cortex_zero.adapters.interface.schemas.platform import (
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformSendSegment,
    PlatformSendSegmentType,
)
from holo_cortex_zero.adapters.utils import adapter_utils
from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.runtime_identity import get_primary_advanced_user_display_name, get_primary_advanced_user_id
from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.models.db_chat_message import DBChatMessage
from holo_cortex_zero.models.db_user import DBUser
from holo_cortex_zero.schemas.agent_ctx import AgentCtx
from holo_cortex_zero.schemas.agent_message import (
    AgentMessageSegment,
    AgentMessageSegmentType,
    convert_agent_message_to_prompt,
)
from holo_cortex_zero.schemas.chat_message import ChatMessage, ChatType
from holo_cortex_zero.services.ai_reply import system_ai_reply_service
from holo_cortex_zero.services.agent.resolver import normalize_bot_surface_text
from holo_cortex_zero.tools.common_util import (
    check_content_trigger,
    check_forbidden_message,
    random_chat_check,
)


class MessageService:
    """消息服务类，处理所有类型的消息推送"""

    _RISK_DISPLAY_NAME = "风险用户"
    _CLEAR_COMMAND = "/clear"
    _CLEAR_ALL_COMMAND = "/clearall"
    _TEST_COMMAND = "/test"
    _CLEAR_ACK_TEXT = "杂乱已清除"
    _CLEAR_ALL_ACK_TEXT = "杂乱与压缩记忆已清除"
    _CLEAR_BUSY_TEXT = "当前还有任务在跑，稍后再清理"

    def __init__(self):
        # 全局状态追踪
        self.running_tasks: Dict[str, asyncio.Task] = {}  # execution_key → 正在执行的agent任务
        self.debounce_timers: Dict[str, float] = {}  # execution_key → 防抖计时器
        self.pending_messages: Dict[str, ChatMessage] = {}  # execution_key → 待处理的最新消息
        self.pending_contexts: Dict[str, Optional[AgentCtx]] = {}  # execution_key → 最新上下文
        self.pending_trigger_sources: Dict[str, str] = {}  # execution_key → human | system

    @staticmethod
    def _normalize_bot_record_text(text: str) -> str:
        return normalize_bot_surface_text(text)

    @staticmethod
    def _is_system_db_message(db_message: DBChatMessage) -> bool:
        sender_id = str(getattr(db_message, "sender_id", "") or "").strip()
        if sender_id != "-1":
            return False

        platform_userid = str(getattr(db_message, "platform_userid", "") or "").strip()
        sender_name = str(getattr(db_message, "sender_name", "") or "").strip().upper()
        sender_nickname = str(getattr(db_message, "sender_nickname", "") or "").strip().upper()
        return platform_userid == "0" or (
            sender_name == "SYSTEM" and sender_nickname == "SYSTEM"
        )

    @staticmethod
    def _trim_bot_edge_echo_by_previous_text(
        *,
        previous_text: str,
        current_text: str,
        window: int = 5,
    ) -> tuple[str, str, str]:
        previous = str(previous_text or "").strip()
        current = str(current_text or "").strip()
        if not previous or not current or window <= 0:
            return current, "", ""

        prefix_source = previous[:window]
        suffix_source = previous[-window:]
        prefix_limit = min(len(prefix_source), len(current))
        prefix_len = 0
        while prefix_len < prefix_limit and prefix_source[prefix_len] == current[prefix_len]:
            prefix_len += 1

        removed_prefix = current[:prefix_len]
        current = current[prefix_len:].strip()

        suffix_limit = min(len(suffix_source), len(current))
        suffix_len = 0
        while suffix_len < suffix_limit and suffix_source[-(suffix_len + 1)] == current[-(suffix_len + 1)]:
            suffix_len += 1

        removed_suffix = current[-suffix_len:] if suffix_len > 0 else ""
        if suffix_len > 0:
            current = current[:-suffix_len].strip()

        return current, removed_prefix, removed_suffix

    async def cleanup_bot_edge_echo_text(self, *, chat_key: str, text: str) -> str:
        normalized = self._normalize_bot_record_text(text)
        if not normalized:
            return ""

        recent_bot_messages = await DBChatMessage.filter(
            chat_key=chat_key,
            sender_id="-1",
            is_recalled=False,
        ).order_by("-id").limit(12)

        previous_text = ""
        for db_message in recent_bot_messages:
            if self._is_system_db_message(db_message):
                continue
            candidate_text = self._normalize_bot_record_text(str(getattr(db_message, "content_text", "") or ""))
            if candidate_text:
                previous_text = candidate_text
                break

        if not previous_text:
            return normalized

        cleaned_text, removed_prefix, removed_suffix = self._trim_bot_edge_echo_by_previous_text(
            previous_text=previous_text,
            current_text=normalized,
        )
        if cleaned_text != normalized:
            logger.info(
                "bot 边界重复字符兜底已执行: chat=%s prev_head=%r prev_tail=%r removed_prefix=%r removed_suffix=%r before=%r after=%r",
                chat_key,
                previous_text[:5],
                previous_text[-5:],
                removed_prefix,
                removed_suffix,
                normalized[:120],
                cleaned_text[:120],
            )
        return cleaned_text

    async def _send_plain_text_to_chat(self, *, chat_key: str, text: str) -> Optional[PlatformSendResponse]:
        try:
            adapter = await adapter_utils.get_adapter_for_chat(chat_key)
            return await adapter.forward_message(
                PlatformSendRequest(
                    chat_key=chat_key,
                    segments=[
                        PlatformSendSegment(
                            type=PlatformSendSegmentType.TEXT,
                            content=str(text or ""),
                        )
                    ],
                )
            )
        except Exception as e:
            logger.error(f"发送纯文本到 {chat_key} 失败: {e}", exc_info=True)
            return None

    @staticmethod
    def _build_bot_record_text(agent_messages: List[AgentMessageSegment]) -> tuple[str, int]:
        """构建 bot 发言的可注入文本，主动跳过附件 transport 标记。"""
        from holo_cortex_zero.services.context_window.manager import context_window_manager

        text_parts: List[str] = []
        skipped_media_count = 0

        for msg in agent_messages:
            if msg.type == AgentMessageSegmentType.TEXT:
                clean_text = context_window_manager.sanitize_model_output_text(str(msg.content or "")).strip()
                if clean_text:
                    text_parts.append(clean_text)
                continue

            skipped_media_count += 1

        return " ".join(text_parts).strip(), skipped_media_count

    @staticmethod
    def _get_message_context_user_id(message: ChatMessage) -> str:
        """提取消息所属的上下文用户 ID。"""
        return str(message.platform_userid or message.sender_id or "").strip()

    @classmethod
    def _is_clear_command(cls, text: Any) -> bool:
        return str(text or "").strip() == cls._CLEAR_COMMAND

    @classmethod
    def _is_clear_all_command(cls, text: Any) -> bool:
        return str(text or "").strip() == cls._CLEAR_ALL_COMMAND

    @classmethod
    def _is_test_command(cls, text: Any) -> bool:
        return str(text or "").strip() == cls._TEST_COMMAND

    @staticmethod
    def _get_message_segment_type(segment: Any) -> str:
        raw_type = segment.get("type") if isinstance(segment, dict) else getattr(segment, "type", "")
        if isinstance(raw_type, str):
            return raw_type.strip()
        return str(getattr(raw_type, "value", raw_type or "")).strip()

    @staticmethod
    def _get_message_segment_text(segment: Any) -> str:
        raw_text = segment.get("text", "") if isinstance(segment, dict) else getattr(segment, "text", "")
        return str(raw_text or "")

    @classmethod
    def _list_message_segment_types(cls, message: ChatMessage) -> List[str]:
        segment_types: List[str] = []
        for segment in list(getattr(message, "content_data", []) or []):
            segment_type = cls._get_message_segment_type(segment)
            if segment_type:
                segment_types.append(segment_type)
        return segment_types

    @classmethod
    def _private_message_has_trigger_text(cls, message: ChatMessage) -> bool:
        segments = list(getattr(message, "content_data", []) or [])
        if segments:
            for segment in segments:
                if cls._get_message_segment_type(segment) != "text":
                    continue
                if cls._get_message_segment_text(segment).strip():
                    return True
            return False
        return bool(str(getattr(message, "content_text", "") or "").strip())

    @staticmethod
    def _load_json_dict(raw_value: Any) -> Dict[str, Any]:
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

    @staticmethod
    def _resolve_notice_sender_name(message: ChatMessage) -> str:
        return str(
            message.sender_nickname
            or message.sender_name
            or message.platform_userid
            or message.sender_id
            or "用户"
        ).strip() or "用户"

    @classmethod
    def _sanitize_protected_sender_identity(
        cls,
        *,
        user_id: Any,
        sender_name: Any,
        sender_nickname: Any,
    ) -> tuple[str, str, bool]:
        normalized_user_id = str(user_id or "").strip()
        normalized_sender_name = str(sender_name or "").strip()
        normalized_sender_nickname = str(sender_nickname or "").strip()
        protected_display_name = get_primary_advanced_user_display_name(config)

        is_protected_alias = (
            normalized_sender_name == protected_display_name
            or normalized_sender_nickname == protected_display_name
        )
        should_sanitize = is_protected_alias and normalized_user_id != get_primary_advanced_user_id(config)

        if not should_sanitize:
            return normalized_sender_name, normalized_sender_nickname, False

        return cls._RISK_DISPLAY_NAME, cls._RISK_DISPLAY_NAME, True

    @classmethod
    def _build_group_trigger_notice_prefix(cls, message: ChatMessage) -> str:
        return "@你；"

    @classmethod
    def _merge_context_notice_ext(
        cls,
        raw_ext_data: Any,
        *,
        prefix: str,
        reason: str,
    ) -> Dict[str, Any]:
        ext_data = cls._load_json_dict(raw_ext_data)
        context_notice = ext_data.get("context_notice")
        if not isinstance(context_notice, dict):
            context_notice = {}
        context_notice["prefix"] = str(prefix or "").strip()
        if reason:
            context_notice["reason"] = reason
        ext_data["context_notice"] = context_notice
        return ext_data

    async def _mark_db_message_context_notice(
        self,
        db_message: Optional[DBChatMessage],
        *,
        prefix: str,
        reason: str,
    ) -> None:
        normalized_prefix = str(prefix or "").strip()
        if not db_message or not normalized_prefix:
            return

        ext_data = self._merge_context_notice_ext(db_message.ext_data, prefix=normalized_prefix, reason=reason)
        current_prefix = str(
            self._load_json_dict(db_message.ext_data).get("context_notice", {}).get("prefix", "")
        ).strip()
        if current_prefix == normalized_prefix:
            return

        db_message.ext_data = json.dumps(ext_data, ensure_ascii=False)
        await db_message.save(update_fields=["ext_data"])
        logger.info(
            "已写入触发上下文前缀: chat=%s msg_id=%s reason=%s prefix=%r",
            getattr(db_message, "chat_key", ""),
            getattr(db_message, "message_id", "") or f"dbid_{getattr(db_message, 'id', 0)}",
            reason,
            normalized_prefix,
        )

    async def _inject_system_notice_into_context(
        self,
        *,
        db_chat_message: DBChatMessage,
        chat_key: str,
        clean_text: str,
        ctx: Optional[AgentCtx],
    ) -> None:
        from holo_cortex_zero.models.db_context_window import DBContextMessage
        from holo_cortex_zero.services.context_window.manager import context_window_manager

        db_chat_channel = await DBChatChannel.get_channel(chat_key=chat_key)

        context_user_id = ""
        if ctx and ctx.db_user:
            context_user_id = str(getattr(ctx.db_user, "platform_userid", "") or "").strip()

        if not context_user_id and db_chat_channel.chat_type == ChatType.PRIVATE:
            channel_id = str(getattr(db_chat_channel, "channel_id", "") or "")
            if channel_id.startswith("private_"):
                context_user_id = channel_id[len("private_"):].strip()

        context_window = await context_window_manager.resolve_context_window(
            user_id=context_user_id,
            chat_key=chat_key,
            adapter_key=db_chat_channel.adapter_key,
        )
        notice_text = f"系统通知。{clean_text}" if clean_text else "系统通知。"
        source_message_id = f"system_push:{getattr(db_chat_message, 'id', 0)}"

        await DBContextMessage.create(
            context_id=context_window.context_id,
            role="user",
            sender_id="system",
            sender_name="system",
            parts_json=json.dumps([{"type": "text", "text": notice_text}], ensure_ascii=False),
            source_chat_key=chat_key,
            source_message_id=source_message_id,
            msg_type="system_inject",
        )
        await context_window_manager.enforce_history_hard_limit(context_window.context_id)
        logger.info(
            "系统触发通知已注入上下文: ctx=%s chat=%s source_message_id=%s text=%r",
            context_window.context_id,
            chat_key,
            source_message_id,
            notice_text[:120],
        )

    async def _build_system_trigger_message(
        self,
        *,
        chat_key: str,
        clean_text: str,
        ctx: Optional[AgentCtx],
        db_chat_channel: DBChatChannel,
    ) -> Optional[ChatMessage]:
        context_user_id = ""
        if ctx and ctx.db_user:
            context_user_id = str(getattr(ctx.db_user, "platform_userid", "") or "").strip()

        if not context_user_id and db_chat_channel.chat_type == ChatType.PRIVATE:
            channel_id = str(getattr(db_chat_channel, "channel_id", "") or "")
            if channel_id.startswith("private_"):
                context_user_id = channel_id[len("private_"):].strip()

        if not context_user_id:
            return None

        return ChatMessage(
            message_id=f"system_trigger:{int(time.time() * 1000)}",
            sender_id=context_user_id,
            sender_name="SYSTEM",
            sender_nickname="SYSTEM",
            adapter_key=db_chat_channel.adapter_key,
            platform_userid=context_user_id,
            is_tome=1,
            is_recalled=False,
            chat_key=chat_key,
            chat_type=db_chat_channel.chat_type,
            content_text=f"系统通知。{clean_text}" if clean_text else "系统通知。",
            content_data=[],
            ext_data={
                "context_notice": {
                    "prefix": "系统通知。",
                    "reason": "system_trigger",
                },
            },
            send_timestamp=int(time.time()),
        )

    def clear_pending_human_trigger(self, execution_key: str, *, reason: str = "") -> bool:
        """清理某个 execution_key 下遗留的人类触发 pending 状态。"""
        if self.pending_trigger_sources.get(execution_key) not in {"", "human"}:
            return False

        removed_message = self.pending_messages.pop(execution_key, None)
        removed_timer = self.debounce_timers.pop(execution_key, None)
        self.pending_contexts.pop(execution_key, None)
        self.pending_trigger_sources.pop(execution_key, None)
        if removed_message is None and removed_timer is None:
            return False

        logger.info(
            "清理遗留 pending 人类触发: "
            f"execution_key={execution_key} reason={reason or 'unknown'} "
            f"has_message={removed_message is not None} has_timer={removed_timer is not None}"
        )
        return True

    def clear_pending_human_triggers_for_context(
        self,
        *,
        context_id: str,
        owner_type: str,
        reason: str = "",
    ) -> int:
        """清理某个上下文窗口下遗留的人类触发 pending，避免 tool 链结束后补触发。"""
        if not context_id:
            return 0

        cleared_count = 1 if self.clear_pending_human_trigger(context_id, reason=reason) else 0

        if cleared_count > 0:
            logger.info(
                "已批量清理上下文窗口的人类触发 pending: "
                f"ctx={context_id} owner_type={owner_type} count={cleared_count} reason={reason or 'unknown'}"
            )

        return cleared_count

    async def _should_swallow_user_trigger(
        self,
        message: ChatMessage,
    ) -> tuple[bool, str, str, str]:
        """判断该用户触发是否应被正在运行的 tool 链吞掉。"""
        from holo_cortex_zero.services.context_window.manager import context_window_manager

        user_id = self._get_message_context_user_id(message)
        if not user_id:
            return False, "", "", ""

        context_window = await context_window_manager.resolve_context_window(
            user_id=user_id,
            chat_key=message.chat_key,
            adapter_key=message.adapter_key,
        )
        if not context_window_manager.is_tool_chain_active(context_window.context_id):
            return False, context_window.context_id, context_window.owner_type, context_window.active_dialog_id or ""

        return True, context_window.context_id, context_window.owner_type, context_window.active_dialog_id or ""

    async def _message_validation_check(self, message: ChatMessage) -> bool:
        """消息校验"""
        plaint_text = message.content_text.strip().replace(" ", "").lower()
        is_fake_message = False

        # 检查伪造消息
        if re.match(r"<.{4,12}\|messageseparator>", plaint_text):
            is_fake_message = True
        if re.match(r"<.{4,12}\|messageseperator>", plaint_text):
            is_fake_message = True

        if "message" in plaint_text and "(id:" in plaint_text:
            is_fake_message = True
        if "from_id:" in plaint_text:  # noqa: SIM103
            is_fake_message = True

        if is_fake_message:
            logger.warning(f"检测到伪造消息: {message.content_text} | 跳过本次处理...")
            return False

        return True

    async def schedule_agent_task(
        self,
        chat_key: Optional[str] = None,
        message: Optional[ChatMessage] = None,
        ctx: Optional[AgentCtx] = None,
        *,
        execution_key: Optional[str] = None,
        source_scope: str = "system",
    ):
        """调度 agent 任务，实现防抖和任务控制"""
        if not message:
            if not chat_key:
                logger.error("调度 Agent 执行失败，目标 chat_key 为空")
                return
            message = ChatMessage.create_empty(chat_key)
        chat_key = message.chat_key
        execution_key = str(execution_key or chat_key or "").strip()
        if not execution_key:
            logger.error(f"调度 Agent 执行失败，execution_key 为空: chat_key={chat_key}")
            return

        is_group_chat = str(getattr(message, "chat_type", "") or "") == ChatType.GROUP.value
        if not is_group_chat and chat_key:
            db_chat_channel = await DBChatChannel.get_or_none(chat_key=chat_key)
            is_group_chat = bool(db_chat_channel and db_chat_channel.chat_type == ChatType.GROUP)

        if is_group_chat and source_scope == "system":
            await system_ai_reply_service.mark_group_judge_active(
                chat_key=chat_key,
                reason="system_schedule",
                source_scope=source_scope,
            )

        current_time = time.time()

        # 更新待处理消息和防抖计时器
        self.pending_messages[execution_key] = message
        self.pending_contexts[execution_key] = ctx
        self.pending_trigger_sources[execution_key] = source_scope
        self.debounce_timers[execution_key] = current_time

        # 如果已有正在执行的任务，直接返回
        if execution_key in self.running_tasks and not self.running_tasks[execution_key].done():
            return

        # 创建防抖任务
        asyncio.create_task(self._debounce_task(execution_key, chat_key, current_time))

    async def _schedule_window_test_reply(
        self,
        *,
        message: ChatMessage,
    ) -> None:
        from holo_cortex_zero.services.context_window.manager import context_window_manager

        # 主干：/test 只切到当前窗口的普通 context，不走高级 context 主线。
        normal_window = await context_window_manager.resolve_context_window(
            user_id="",
            chat_key=message.chat_key,
            adapter_key=message.adapter_key,
        )
        await context_window_manager.update_anchor(normal_window.context_id, message.chat_key)

        normal_ctx = await AgentCtx.create_by_chat_key(chat_key=message.chat_key)
        empty_message = ChatMessage.create_empty(message.chat_key)

        logger.info(
            "advanced test command scheduled normal context reply without message record: "
            f"ctx={normal_window.context_id} chat={message.chat_key} trigger_user={self._get_message_context_user_id(message) or '<empty>'}"
        )
        await self.schedule_agent_task(
            message=empty_message,
            ctx=normal_ctx,
            execution_key=normal_window.context_id,
            source_scope="system",
        )

    async def _debounce_task(self, execution_key: str, chat_key: str, start_time: float):
        """防抖任务处理

        Args:
            execution_key (str): 触发执行键
            chat_key (str): 频道标识
            start_time (float): 任务开始时间
        """
        db_chat_channel = await DBChatChannel.get(chat_key=chat_key)
        # 等待防抖时间
        await asyncio.sleep(config.AI_DEBOUNCE_WAIT_SECONDS)

        # 检查是否在防抖期间有新消息
        current_timer = self.debounce_timers.get(execution_key)
        if current_timer is None or start_time != current_timer:
            return

        # 获取最终要处理的消息
        final_message = self.pending_messages.pop(execution_key, None)
        final_ctx = self.pending_contexts.pop(execution_key, None)
        self.pending_trigger_sources.pop(execution_key, None)
        if not final_message:
            return

        # 创建新的agent任务
        task = asyncio.create_task(
            self._run_chat_agent_task(
                execution_key=execution_key,
                chat_key=chat_key,
                message=final_message if not final_message.is_empty() else None,
                ctx=final_ctx,
            ),
        )
        self.running_tasks[execution_key] = task

    async def _run_chat_agent_task(
        self,
        *,
        execution_key: str,
        chat_key: str,
        message: Optional[ChatMessage] = None,
        ctx: Optional[AgentCtx] = None,
    ):
        """执行agent任务

        统一走新架构 run_agent_v2。
        """
        adapter = await adapter_utils.get_adapter_for_chat(chat_key)

        logger.info(f"Message From {chat_key} is ToMe, Running Chat Agent (v2)...")

        processing_with_emoji = bool(getattr(adapter.config, "SESSION_PROCESSING_WITH_EMOJI", False))

        # 设置处理emoji
        if message and processing_with_emoji and message.message_id:
            await adapter.set_message_reaction(message.message_id, True)

        try:
            from holo_cortex_zero.services.agent.run_agent_v2 import run_agent_v2

            try:
                await run_agent_v2(chat_key=chat_key, chat_message=message, ctx=ctx)
            except Exception as e:
                logger.exception(f"run_agent_v2 执行失败: {e}")
        finally:
            # 清理任务状态
            if execution_key in self.running_tasks:
                del self.running_tasks[execution_key]

            final_message = self.pending_messages.pop(execution_key, None)
            final_ctx = self.pending_contexts.pop(execution_key, None)
            self.pending_trigger_sources.pop(execution_key, None)
            self.debounce_timers.pop(execution_key, None)

            # 取消处理emoji（如果设置过）
            if processing_with_emoji and message and message.message_id:
                await adapter.set_message_reaction(message.message_id, False)

            # 如果有待处理消息，创建新的任务处理最后一条消息
            if final_message:
                next_chat_key = final_message.chat_key or chat_key
                new_task = asyncio.create_task(
                    self._run_chat_agent_task(
                        execution_key=execution_key,
                        chat_key=next_chat_key,
                        message=final_message if not final_message.is_empty() else None,
                        ctx=final_ctx,
                    )
                )
                self.running_tasks[execution_key] = new_task

    async def push_human_message(
        self,
        message: ChatMessage,
        user: Optional[DBUser] = None,
        trigger_agent: bool = False,
        db_chat_channel: Optional[DBChatChannel] = None,
    ):
        """推送人类用户消息"""
        db_chat_channel = db_chat_channel or await DBChatChannel.get_channel(chat_key=message.chat_key)
        persona_name = db_chat_channel.get_persona_display_name()

        if not await self._message_validation_check(message):
            logger.warning("消息校验失败，跳过本次处理...")
            return

        content_data = [o.model_dump() for o in message.content_data]
        from holo_cortex_zero.services.advanced_context_mode import advanced_context_mode_service

        mode_command = advanced_context_mode_service.parse_mode_command(message.content_text)
        clear_command = self._is_clear_command(message.content_text)
        clear_all_command = self._is_clear_all_command(message.content_text)
        test_command = self._is_test_command(message.content_text)

        if not mode_command and not clear_command and not clear_all_command and not test_command and check_forbidden_message(message.content_text, config):
            logger.info(f"消息 {message.content_text} 被禁止，跳过本次处理...")
            return

        sanitized_sender_name, sanitized_sender_nickname, identity_sanitized = self._sanitize_protected_sender_identity(
            user_id=message.platform_userid or message.sender_id,
            sender_name=message.sender_name,
            sender_nickname=message.sender_nickname,
        )
        if identity_sanitized:
            logger.warning(
                "检测到受保护昵称伪装，已在上下文入口前清洗: user_id=%s chat_key=%s message_id=%s raw_sender_name=%r raw_sender_nickname=%r sanitized=%s",
                str(message.platform_userid or message.sender_id or "").strip(),
                message.chat_key,
                message.message_id,
                message.sender_name,
                message.sender_nickname,
                sanitized_sender_name,
            )
            message.sender_name = sanitized_sender_name
            message.sender_nickname = sanitized_sender_nickname

        ctx: AgentCtx = await AgentCtx.create_by_chat_key(chat_key=message.chat_key)
        ctx._trigger_db_user = user  # noqa: SLF001

        from holo_cortex_zero.services.context_window.manager import context_window_manager

        context_window = None
        context_id = message.chat_key
        owner_type = "normal"
        active_dialog_id = ""
        context_user_id = self._get_message_context_user_id(message)
        if (mode_command or clear_command or clear_all_command or test_command) and not context_window_manager._is_advanced_sender(context_user_id):
            command_text = (
                mode_command.command if mode_command else
                self._TEST_COMMAND if test_command else
                self._CLEAR_ALL_COMMAND if clear_all_command else
                self._CLEAR_COMMAND
            )
            logger.info(
                "normal context command ignored: "
                f"chat={message.chat_key} user_id={context_user_id or '<empty>'} command={command_text}"
            )
            return

        if context_user_id:
            try:
                context_window = await context_window_manager.resolve_context_window(
                    user_id=context_user_id,
                    chat_key=message.chat_key,
                    adapter_key=message.adapter_key,
                )
                context_id = context_window.context_id
                owner_type = context_window.owner_type
                active_dialog_id = context_window.active_dialog_id or ""
            except Exception as e:
                logger.error(f"解析上下文窗口失败，回退 chat_key 调度: {e}", exc_info=True)

        if test_command:
            # 分支兼容：高级用户可手动触发当前群聊普通 context 回复，但不落消息记录。
            await self._schedule_window_test_reply(message=message)
            return

        if clear_command or clear_all_command:
            command_text = self._CLEAR_ALL_COMMAND if clear_all_command else self._CLEAR_COMMAND
            if not context_window or not context_window_manager.is_advanced_window(context_window):
                logger.info(
                    "normal context command ignored: "
                    f"chat={message.chat_key} user_id={context_user_id or '<empty>'} command={command_text}"
                )
                return

            running_agent_active = any(not task.done() for task in self.running_tasks.values())
            if running_agent_active or await context_window_manager.has_any_tool_chain_active():
                await self._send_plain_text_to_chat(chat_key=message.chat_key, text=self._CLEAR_BUSY_TEXT)
                logger.info(
                    "advanced context clear command ignored by active runtime: "
                    f"ctx={context_window.context_id} chat={message.chat_key} "
                    f"command={command_text} "
                    f"running_agent_active={running_agent_active} "
                    f"active_dialog={context_window.active_dialog_id or ''}"
                )
                return

            clear_result = await context_window_manager.clear_all_message_and_context_records(
                context_window,
                dialog_chat_key=message.chat_key,
                clear_compressed_summary=clear_all_command,
            )
            self.pending_messages.clear()
            self.pending_contexts.clear()
            self.pending_trigger_sources.clear()
            self.debounce_timers.clear()
            await self._send_plain_text_to_chat(
                chat_key=message.chat_key,
                text=self._CLEAR_ALL_ACK_TEXT if clear_all_command else self._CLEAR_ACK_TEXT,
            )
            logger.info(
                "advanced context clear command applied: "
                f"ctx={context_window.context_id} chat={message.chat_key} command={command_text} result={clear_result}"
            )
            return

        if mode_command:
            if not context_window or not context_window_manager.is_advanced_window(context_window):
                logger.info(
                    "normal context command ignored: "
                    f"chat={message.chat_key} user_id={context_user_id or '<empty>'} command={mode_command.command}"
                )
                return

            ack_text = mode_command.ack_text
            if context_window_manager.is_tool_chain_active(context_window.context_id):
                await self._send_plain_text_to_chat(chat_key=message.chat_key, text=ack_text)
                logger.info(
                    "advanced context mode command ignored by active tool chain: "
                    f"ctx={context_window.context_id} chat={message.chat_key} mode={mode_command.name} "
                    f"active_dialog={context_window.active_dialog_id or ''}"
                )
                return

            await context_window_manager.set_advanced_context_mode(
                context_window,
                mode=mode_command.name,
                source="manual",
                dialog_chat_key=message.chat_key,
            )
            await self._send_plain_text_to_chat(chat_key=message.chat_key, text=ack_text)
            logger.info(
                "advanced context mode command applied: "
                f"ctx={context_window.context_id} chat={message.chat_key} mode={mode_command.name} source=manual"
            )
            return

        if (
            context_window
            and context_window_manager.is_advanced_window(context_window)
            and not context_window_manager.is_tool_chain_active(context_window.context_id)
        ):
            await context_window_manager.apply_advanced_dialog_default_if_needed(
                context_window,
                dialog_chat_key=message.chat_key,
                chat_type=str(message.chat_type or ""),
            )
            active_dialog_id = context_window.active_dialog_id or ""

        # 添加聊天记录
        db_message = await DBChatMessage.create(
            message_id=message.message_id,
            sender_id=message.sender_id,
            sender_name=message.sender_name,
            sender_nickname=message.sender_nickname,
            adapter_key=message.adapter_key,
            platform_userid=message.platform_userid,
            is_tome=message.is_tome,
            is_recalled=message.is_recalled,
            chat_key=message.chat_key,
            chat_type=message.chat_type,
            content_text=message.content_text,
            content_data=json.dumps(content_data, ensure_ascii=False),
            ext_data=json.dumps(message.ext_data, ensure_ascii=False),
            send_timestamp=int(time.time()),  # 使用处理后的时间戳
        )

        should_ignore = (user and user.is_prevent_trigger) or (user and not user.is_active)

        if context_window and context_window_manager.is_tool_chain_active(context_id):
            self.clear_pending_human_triggers_for_context(
                context_id=context_id,
                owner_type=owner_type,
                reason=f"tool_chain_active@{active_dialog_id or message.chat_key}",
            )
            logger.info(
                "用户触发已被 tool 链严格吞掉，仅保留聊天消息入库供后续上下文吸收: "
                f"ctx={context_id} chat={message.chat_key} active_dialog={active_dialog_id or message.chat_key} "
                f"is_tome={bool(message.is_tome)} text={message.content_text[:120]}"
            )
            return

        if should_ignore:
            return

        if not db_chat_channel.is_active:
            logger.info(f"聊天频道 {message.chat_key} 已被禁用，跳过本次处理...")
            return

        is_private_chat = str(message.chat_type or "") == ChatType.PRIVATE.value
        is_group_chat = str(message.chat_type or "") == ChatType.GROUP.value
        persona_triggered = bool(persona_name and persona_name in message.content_text)
        content_triggered = check_content_trigger(message.content_text, config)
        random_triggered = random_chat_check(config)
        private_segment_types = self._list_message_segment_types(message) if is_private_chat else []
        has_private_trigger_text = self._private_message_has_trigger_text(message) if is_private_chat else False

        group_direct_trigger_reason = ""
        if is_group_chat:
            if bool(message.is_tome):
                group_direct_trigger_reason = "mention_or_to_me"
            elif persona_triggered:
                group_direct_trigger_reason = "persona_name"
            elif content_triggered:
                group_direct_trigger_reason = "keyword_regex"
            elif random_triggered:
                group_direct_trigger_reason = "random_probability"

        if trigger_agent:
            if is_group_chat:
                if bool(message.is_tome):
                    await self._mark_db_message_context_notice(
                        db_message,
                        prefix=self._build_group_trigger_notice_prefix(message),
                        reason="mention_or_to_me",
                    )
                elif content_triggered:
                    await self._mark_db_message_context_notice(
                        db_message,
                        prefix=self._build_group_trigger_notice_prefix(message),
                        reason="keyword_regex",
                    )
            if is_group_chat:
                await system_ai_reply_service.mark_group_judge_active(
                    chat_key=message.chat_key,
                    reason="trigger_agent",
                    source_scope="human",
                )
            await self.schedule_agent_task(
                message=message,
                ctx=ctx,
                execution_key=context_id or message.chat_key,
                source_scope="human",
            )
            return

        if is_private_chat and not has_private_trigger_text:
            logger.info(
                "私聊消息已入库但不触发回复，不启动本轮上下文组装: "
                f"ctx={context_id or message.chat_key} chat={message.chat_key} owner_type={owner_type} "
                f"message_id={message.message_id or f'dbid_{db_message.id}'} "
                f"segment_types={','.join(private_segment_types) or 'none'} "
                f"content_text_len={len(str(message.content_text or ''))}"
            )
            return

        # 主干固定启用系统 ai_reply 入口；字段仅保留为旧配置兼容，群聊 judge 仍由 AI_REPLY_JUDGE_ENABLED 单独控制。
        if is_private_chat:
            logger.info(
                "系统 ai_reply 私聊直通触发: "
                f"ctx={context_id or message.chat_key} chat={message.chat_key} owner_type={owner_type} has_trigger_text={has_private_trigger_text}"
            )
            await self.schedule_agent_task(
                message=message,
                ctx=ctx,
                execution_key=context_id or message.chat_key,
                source_scope="human",
            )
            return

        if is_group_chat and group_direct_trigger_reason:
            if group_direct_trigger_reason in {"mention_or_to_me", "keyword_regex"}:
                await self._mark_db_message_context_notice(
                    db_message,
                    prefix=self._build_group_trigger_notice_prefix(message),
                    reason=group_direct_trigger_reason,
                )
            await system_ai_reply_service.mark_group_judge_active(
                chat_key=message.chat_key,
                reason=group_direct_trigger_reason,
                source_scope="human",
            )
            logger.info(
                "系统 ai_reply 群聊主动触发直通，跳过 judge: "
                f"trigger_chat={message.chat_key} exec_ctx={context_id or message.chat_key} owner_type={owner_type} reason={group_direct_trigger_reason} is_tome={bool(message.is_tome)}"
            )
            await self.schedule_agent_task(
                message=message,
                ctx=ctx,
                execution_key=context_id or message.chat_key,
                source_scope="human",
            )
            return

        if is_group_chat and bool(getattr(config, "AI_REPLY_JUDGE_ENABLED", True)):
            if context_window is None:
                logger.warning(
                    "系统 ai_reply 群聊判断缺少上下文窗口，按默认策略不触发: "
                    f"chat={message.chat_key}"
                )
                return

            judge_window_decision = await system_ai_reply_service.get_group_judge_window_decision(
                chat_key=message.chat_key,
            )
            if not judge_window_decision.should_run_judge:
                logger.info(
                    "系统 ai_reply 群聊 judge 窗口未开启，跳过本次 LLM 判断: "
                    f"ctx={context_id} chat={message.chat_key} source={judge_window_decision.source} "
                    f"last_trigger_ts={judge_window_decision.last_trigger_ts}"
                )
                return

            logger.info(
                "系统 ai_reply 群聊 judge 窗口命中，开始 LLM 判断: "
                f"ctx={context_id} chat={message.chat_key} remaining_seconds={judge_window_decision.remaining_seconds}"
            )

            judge_decision = await system_ai_reply_service.should_reply_for_message(
                message=message,
                context_window=context_window,
            )
            if judge_decision.should_reply:
                await self._mark_db_message_context_notice(
                    db_message,
                    prefix=self._build_group_trigger_notice_prefix(message),
                    reason="judge_decision_true",
                )
                logger.info(
                    "系统 ai_reply 群聊判断为 true，进入执行层上下文路由: "
                    f"trigger_chat={message.chat_key} exec_ctx={context_id or message.chat_key} owner_type={owner_type}"
                )
                await self.schedule_agent_task(
                    message=message,
                    ctx=ctx,
                    execution_key=context_id or message.chat_key,
                    source_scope="human",
                )
            else:
                logger.info(
                    "系统 ai_reply 群聊判断为 false，本次不触发 agent: "
                    f"ctx={context_id} chat={message.chat_key} source={judge_decision.source}"
                )
            return

        # 检查是否需要触发回复
        should_trigger = (
            persona_triggered
            or bool(message.is_tome)
            or random_triggered
            or content_triggered
        )

        if should_trigger:
            if is_group_chat:
                if bool(message.is_tome):
                    await self._mark_db_message_context_notice(
                        db_message,
                        prefix=self._build_group_trigger_notice_prefix(message),
                        reason="legacy_mention_or_to_me",
                    )
                elif content_triggered:
                    await self._mark_db_message_context_notice(
                        db_message,
                        prefix=self._build_group_trigger_notice_prefix(message),
                        reason="legacy_keyword_regex",
                    )
            if is_group_chat:
                await system_ai_reply_service.mark_group_judge_active(
                    chat_key=message.chat_key,
                    reason=group_direct_trigger_reason or "legacy_should_trigger",
                    source_scope="human",
                )
            await self.schedule_agent_task(
                message=message,
                ctx=ctx,
                execution_key=context_id or message.chat_key,
                source_scope="human",
            )

    async def push_bot_message(
        self,
        chat_key: str,
        agent_messages: Union[str, List[AgentMessageSegment]],
        plt_response: Optional[PlatformSendResponse] = None,
        db_chat_channel: Optional[DBChatChannel] = None,
        ref_msg_id: Optional[str] = None,
    ):
        """推送机器人消息"""
        logger.info(f"Pushing Bot Message To Chat {chat_key}")
        db_chat_channel = db_chat_channel or await DBChatChannel.get_channel(chat_key=chat_key)
        persona_name = db_chat_channel.get_persona_display_name()

        if isinstance(agent_messages, str):
            agent_messages = [AgentMessageSegment(type=AgentMessageSegmentType.TEXT, content=agent_messages)]

        from holo_cortex_zero.services.context_window.manager import context_window_manager

        sanitized_messages: List[AgentMessageSegment] = []
        for msg in agent_messages:
            if msg.type == AgentMessageSegmentType.TEXT:
                clean_content = self._normalize_bot_record_text(
                    context_window_manager.sanitize_model_output_text(str(msg.content or ""))
                )
                sanitized_messages.append(
                    AgentMessageSegment(
                        type=AgentMessageSegmentType.TEXT,
                        content=clean_content,
                    )
                )
            else:
                sanitized_messages.append(msg)
        agent_messages = sanitized_messages

        content_text, skipped_media_count = self._build_bot_record_text(agent_messages)
        content_text = self._normalize_bot_record_text(content_text)
        if skipped_media_count > 0:
            logger.info(
                "Bot 附件消息已跳过上下文文本落库，避免 send_file/send_image transport 路径回灌: "
                f"chat={chat_key} skipped_media={skipped_media_count} text_chars={len(content_text)}"
            )

        content_data = []
        for msg in agent_messages:
            if msg.type == AgentMessageSegmentType.FILE:
                file_path = Path(msg.content)
                if file_path.exists():
                    mime_type = magic.from_buffer(file_path.read_bytes(), mime=True)
                    file_name = file_path.name
                    if mime_type.startswith("image/"):
                        content_data.append(
                            {
                                "type": "image",
                                "text": "",
                                "file_name": file_name,
                                "local_path": str(file_path),
                                "remote_url": "",
                            },
                        )
                    else:
                        content_data.append(
                            {
                                "type": "file",
                                "text": "",
                                "file_name": file_name,
                                "local_path": str(file_path),
                                "remote_url": "",
                            },
                        )
            elif msg.type == AgentMessageSegmentType.TEXT:
                content_data.append(
                    {
                        "type": "text",
                        "text": msg.content,
                    },
                )

        adapter = adapter_utils.get_adapter(db_chat_channel.adapter_key)
        await DBChatMessage.create(
            message_id=plt_response.message_id if plt_response and plt_response.message_id else "",
            sender_id=-1,
            sender_name=persona_name,
            sender_nickname=persona_name,
            adapter_key=db_chat_channel.adapter_key,
            platform_userid=(await adapter.get_self_info()).user_id,
            is_tome=0,
            is_recalled=False,
            chat_key=chat_key,
            chat_type=db_chat_channel.chat_type,
            content_text=content_text,
            content_data=json.dumps(content_data, ensure_ascii=False),
            ext_data=json.dumps(PlatformMessageExt(ref_msg_id=ref_msg_id or "").model_dump(), ensure_ascii=False),
            send_timestamp=int(time.time()),
        )

        if db_chat_channel.chat_type == ChatType.GROUP:
            await system_ai_reply_service.mark_group_judge_active(
                chat_key=chat_key,
                reason="bot_reply",
                source_scope="system",
            )
            logger.info("系统 ai_reply 群聊 bot 回复完成，已续期 judge 窗口: chat={}", chat_key)

    async def push_bot_message_text_shadow(
        self,
        chat_key: str,
        text: str,
        plt_response: Optional[PlatformSendResponse] = None,
        db_chat_channel: Optional[DBChatChannel] = None,
        ref_msg_id: Optional[str] = None,
    ):
        """推送仅保留文本语义的 bot shadow 记录。"""
        logger.info(f"Pushing Bot Text Shadow To Chat {chat_key}")
        db_chat_channel = db_chat_channel or await DBChatChannel.get_channel(chat_key=chat_key)
        persona_name = db_chat_channel.get_persona_display_name()

        from holo_cortex_zero.services.context_window.manager import context_window_manager

        clean_text = self._normalize_bot_record_text(
            context_window_manager.sanitize_model_output_text(str(text or ""))
        )
        adapter = adapter_utils.get_adapter(db_chat_channel.adapter_key)
        await DBChatMessage.create(
            message_id=plt_response.message_id if plt_response and plt_response.message_id else "",
            sender_id=-1,
            sender_name=persona_name,
            sender_nickname=persona_name,
            adapter_key=db_chat_channel.adapter_key,
            platform_userid=(await adapter.get_self_info()).user_id,
            is_tome=0,
            is_recalled=False,
            chat_key=chat_key,
            chat_type=db_chat_channel.chat_type,
            content_text=clean_text,
            content_data=json.dumps([], ensure_ascii=False),
            ext_data=json.dumps(PlatformMessageExt(ref_msg_id=ref_msg_id or "").model_dump(), ensure_ascii=False),
            send_timestamp=int(time.time()),
        )

        if db_chat_channel.chat_type == ChatType.GROUP:
            await system_ai_reply_service.mark_group_judge_active(
                chat_key=chat_key,
                reason="bot_reply_text_shadow",
                source_scope="system",
            )
            logger.info("系统 ai_reply 群聊 bot 文本影子回复完成，已续期 judge 窗口: chat={}", chat_key)

    async def push_system_message(
        self,
        chat_key: str,
        agent_messages: Union[str, List[AgentMessageSegment]],
        trigger_agent: bool = False,
        db_chat_channel: Optional[DBChatChannel] = None,
        ctx: Optional[AgentCtx] = None,
    ):
        """推送系统消息"""
        logger.info(f"Pushing System Message To Chat {chat_key}")
        db_chat_channel = db_chat_channel or await DBChatChannel.get_channel(chat_key=chat_key)

        if isinstance(agent_messages, str):
            agent_messages = [AgentMessageSegment(type=AgentMessageSegmentType.TEXT, content=agent_messages)]

        content_text = convert_agent_message_to_prompt(agent_messages)

        ctx = ctx or await AgentCtx.create_by_chat_key(chat_key=chat_key)
        ext_payload: Dict[str, Any] = {}
        if trigger_agent:
            ext_payload = self._merge_context_notice_ext(
                ext_payload,
                prefix="系统通知。",
                reason="system_trigger",
            )

        db_chat_message = await DBChatMessage.create(
            message_id="",
            sender_id=-1,
            sender_name="SYSTEM",
            sender_nickname="SYSTEM",
            adapter_key=db_chat_channel.adapter_key,
            platform_userid="0",
            is_tome=1 if trigger_agent else 0,
            is_recalled=False,
            chat_key=chat_key,
            chat_type=db_chat_channel.chat_type,
            content_text=content_text,
            content_data=json.dumps([], ensure_ascii=False),
            ext_data=json.dumps(ext_payload, ensure_ascii=False),
            send_timestamp=int(time.time()),
        )

        if trigger_agent:
            if not db_chat_channel.is_active:
                logger.info(f"聊天频道 {chat_key} 已被禁用，跳过本次处理...")
                return
            await self._inject_system_notice_into_context(
                db_chat_message=db_chat_message,
                chat_key=chat_key,
                clean_text=content_text,
                ctx=ctx,
            )
            synthetic_message = await self._build_system_trigger_message(
                chat_key=chat_key,
                clean_text=content_text,
                ctx=ctx,
                db_chat_channel=db_chat_channel,
            )
            if synthetic_message is not None:
                await self.schedule_agent_task(
                    message=synthetic_message,
                    ctx=ctx,
                    execution_key=self._get_message_context_user_id(synthetic_message) or chat_key,
                    source_scope="system",
                )
            else:
                await self.schedule_agent_task(chat_key=chat_key, ctx=ctx)


# 全局消息服务实例
message_service = MessageService()
