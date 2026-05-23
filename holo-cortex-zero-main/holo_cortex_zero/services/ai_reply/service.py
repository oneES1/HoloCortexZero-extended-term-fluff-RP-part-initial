from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import APP_SYSTEM_DIR
from holo_cortex_zero.core.runtime_identity import get_bot_persona_display_name, get_primary_advanced_user_display_name
from holo_cortex_zero.models.db_chat_message import DBChatMessage
from holo_cortex_zero.models.db_context_window import DBContextMessage, DBContextWindow
from holo_cortex_zero.schemas.chat_message import ChatMessage
from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn
from holo_cortex_zero.services.context_window.manager import context_window_manager
from holo_cortex_zero.services.llm.auxiliary import generate_auxiliary
from holo_cortex_zero.services.llm.model_group_params import build_model_group_extra_params
from holo_cortex_zero.services.llm.qwen_compat import _extract_json_object


_MEDIA_PLACEHOLDER_RE = re.compile(r"^(?:.+发送的(?:图|音频|视频|文件)|\[音频:|\[视频:|\[文件:|\[图片:|\[历史图片)")


def _is_advanced_user_path_notice(line: str) -> bool:
    pattern = rf"^{re.escape(get_primary_advanced_user_display_name(config))}发送(?:\s+/workspace(?:/.*)?)?$"
    return bool(re.match(pattern, str(line or "")))

@dataclass(slots=True)
class ReplyJudgeDecision:
    should_reply: bool
    source: str
    raw_json: str = ""


@dataclass(slots=True)
class MultimodalRouteDecision:
    should_route_multimodal: bool
    matched_pattern: str = ""
    scanned_messages: int = 0


@dataclass(slots=True)
class GroupJudgeWindowDecision:
    should_run_judge: bool
    source: str
    remaining_seconds: int = 0
    last_trigger_ts: int = 0


class SystemAIReplyService:
    def __init__(self) -> None:
        self._group_judge_window_lock = asyncio.Lock()
        self._group_judge_window_cache: Optional[dict[str, int]] = None

    async def initialize_runtime(self) -> None:
        logger.info(
            "系统 ai_reply 服务初始化: "
            "enabled=True "
            f"judge_enabled={bool(getattr(config, 'AI_REPLY_JUDGE_ENABLED', True))} "
            f"multimodal_regex_enabled=True"
        )

    @staticmethod
    def _group_judge_window_store_path() -> Path:
        return Path(APP_SYSTEM_DIR) / "ai_reply" / "group_judge_window.json"

    @staticmethod
    def _group_judge_window_seconds() -> int:
        return max(int(getattr(config, "AI_REPLY_JUDGE_ACTIVE_WINDOW_SECONDS", 1800) or 0), 0)

    def _load_group_judge_window_cache_unlocked(self) -> dict[str, int]:
        if self._group_judge_window_cache is not None:
            return self._group_judge_window_cache

        path = self._group_judge_window_store_path()
        if not path.exists():
            self._group_judge_window_cache = {}
            return self._group_judge_window_cache

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("ai_reply 读取群聊 judge 窗口状态失败，已回退为空: err={}", f"{type(exc).__name__}: {exc}")
            self._group_judge_window_cache = {}
            return self._group_judge_window_cache

        if not isinstance(payload, dict):
            logger.warning("ai_reply 群聊 judge 窗口状态格式异常，已回退为空")
            self._group_judge_window_cache = {}
            return self._group_judge_window_cache

        normalized: dict[str, int] = {}
        for chat_key, raw_ts in payload.items():
            key = str(chat_key or "").strip()
            if not key:
                continue
            try:
                ts_value = int(raw_ts or 0)
            except Exception:
                continue
            if ts_value > 0:
                normalized[key] = ts_value
        self._group_judge_window_cache = normalized
        return self._group_judge_window_cache

    def _prune_group_judge_window_cache_unlocked(self, *, now_ts: int, window_seconds: int) -> bool:
        cache = self._load_group_judge_window_cache_unlocked()
        if not cache:
            return False

        if window_seconds <= 0:
            if cache:
                cache.clear()
                return True
            return False

        expired_keys = [chat_key for chat_key, last_trigger_ts in cache.items() if now_ts - int(last_trigger_ts or 0) >= window_seconds]
        if not expired_keys:
            return False

        for chat_key in expired_keys:
            cache.pop(chat_key, None)
        return True

    def _save_group_judge_window_cache_unlocked(self) -> None:
        path = self._group_judge_window_store_path()
        cache = self._load_group_judge_window_cache_unlocked()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        except Exception as exc:
            logger.warning("ai_reply 持久化群聊 judge 窗口状态失败: err={}", f"{type(exc).__name__}: {exc}")

    async def mark_group_judge_active(self, *, chat_key: str, reason: str, source_scope: str) -> None:
        normalized_chat_key = str(chat_key or "").strip()
        if not normalized_chat_key:
            return

        window_seconds = self._group_judge_window_seconds()
        if window_seconds <= 0:
            logger.info(
                "ai_reply 群聊 judge 窗口已禁用，跳过激活记录: chat={} source_scope={} reason={}",
                normalized_chat_key,
                source_scope,
                reason,
            )
            return

        now_ts = int(time.time())
        async with self._group_judge_window_lock:
            cache = self._load_group_judge_window_cache_unlocked()
            changed = self._prune_group_judge_window_cache_unlocked(now_ts=now_ts, window_seconds=window_seconds)
            cache[normalized_chat_key] = now_ts
            self._save_group_judge_window_cache_unlocked()

        logger.info(
            "ai_reply 群聊 judge 窗口已激活: chat={} source_scope={} reason={} ttl_seconds={} pruned_expired={}",
            normalized_chat_key,
            source_scope,
            reason,
            window_seconds,
            changed,
        )

    async def get_group_judge_window_decision(self, *, chat_key: str) -> GroupJudgeWindowDecision:
        normalized_chat_key = str(chat_key or "").strip()
        if not normalized_chat_key:
            return GroupJudgeWindowDecision(False, "chat_key_missing", 0, 0)

        window_seconds = self._group_judge_window_seconds()
        if window_seconds <= 0:
            return GroupJudgeWindowDecision(True, "window_disabled", 0, 0)

        now_ts = int(time.time())
        async with self._group_judge_window_lock:
            cache = self._load_group_judge_window_cache_unlocked()
            changed = self._prune_group_judge_window_cache_unlocked(now_ts=now_ts, window_seconds=window_seconds)
            last_trigger_ts = int(cache.get(normalized_chat_key, 0) or 0)
            if changed:
                self._save_group_judge_window_cache_unlocked()

        if last_trigger_ts <= 0:
            return GroupJudgeWindowDecision(False, "inactive_window", 0, 0)

        elapsed_seconds = max(now_ts - last_trigger_ts, 0)
        remaining_seconds = max(window_seconds - elapsed_seconds, 0)
        if remaining_seconds <= 0:
            async with self._group_judge_window_lock:
                cache = self._load_group_judge_window_cache_unlocked()
                if cache.pop(normalized_chat_key, None) is not None:
                    self._save_group_judge_window_cache_unlocked()
            return GroupJudgeWindowDecision(False, "expired_window", 0, last_trigger_ts)

        return GroupJudgeWindowDecision(True, "active_window", remaining_seconds, last_trigger_ts)

    @staticmethod
    def _normalize_plaintext(text: str) -> str:
        cleaned = context_window_manager.sanitize_model_output_text(str(text or ""))
        if not cleaned:
            return ""

        kept_lines: List[str] = []
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if _is_advanced_user_path_notice(line):
                continue
            if _MEDIA_PLACEHOLDER_RE.match(line):
                continue
            kept_lines.append(line)
        return "\n".join(kept_lines).strip()

    @staticmethod
    def _format_history_line(db_msg: DBChatMessage, text: str) -> str:
        ts = datetime.fromtimestamp(int(getattr(db_msg, "send_timestamp", 0) or 0)).strftime("%m-%d %H:%M:%S")
        sender_name = str(getattr(db_msg, "sender_nickname", None) or getattr(db_msg, "sender_name", None) or "未知")
        sender_id = str(getattr(db_msg, "platform_userid", None) or getattr(db_msg, "sender_id", "") or "")
        speaker = "bot" if str(getattr(db_msg, "sender_id", "")).strip() == "-1" else "user"
        if speaker == "bot":
            return f"[{ts}] {speaker}({sender_id}|{sender_name}): {text}"
        return f"[{ts}] {speaker}({sender_id}): {text}"

    async def _locate_current_db_chat_message(
        self,
        *,
        chat_key: str,
        current_message: ChatMessage,
    ) -> Optional[DBChatMessage]:
        message_id = str(current_message.message_id or "").strip()
        sender_id = str(current_message.sender_id or "").strip()
        if message_id and sender_id:
            matched = await DBChatMessage.filter(
                chat_key=chat_key,
                message_id=message_id,
                sender_id=sender_id,
            ).order_by("-id").first()
            if matched is not None:
                return matched

        send_timestamp = int(getattr(current_message, "send_timestamp", 0) or 0)
        if sender_id and send_timestamp > 0:
            matched = await DBChatMessage.filter(
                chat_key=chat_key,
                sender_id=sender_id,
                send_timestamp=send_timestamp,
            ).order_by("-id").first()
            if matched is not None:
                return matched

        return None

    async def _collect_reply_judge_plaintext_history(
        self,
        *,
        chat_key: str,
        current_message: ChatMessage,
        max_messages: int,
    ) -> List[str]:
        fetch_limit = max(int(max_messages or 0) * 4, int(max_messages or 0) + 4, 16)
        current_db_msg = await self._locate_current_db_chat_message(
            chat_key=chat_key,
            current_message=current_message,
        )
        base_query = DBChatMessage.filter(chat_key=chat_key)
        if current_db_msg is not None:
            candidates = await base_query.filter(id__lt=int(current_db_msg.id)).order_by("-id").limit(fetch_limit).all()
        else:
            logger.warning(
                "ai_reply judge 未定位当前 DBChatMessage，历史裁剪回退到最新窗口: chat={} message_id={} sender_id={}",
                chat_key,
                str(current_message.message_id or "").strip(),
                str(current_message.sender_id or "").strip(),
            )
            candidates = await base_query.order_by("-id").limit(fetch_limit).all()

        lines: List[str] = []
        current_key = (
            str(current_message.message_id or "").strip(),
            str(current_message.sender_id or "").strip(),
        )
        for db_msg in candidates:
            candidate_key = (
                str(getattr(db_msg, "message_id", "") or "").strip(),
                str(getattr(db_msg, "sender_id", "") or "").strip(),
            )
            if candidate_key == current_key:
                continue

            text = self._normalize_plaintext(str(getattr(db_msg, "content_text", "") or ""))
            if not text:
                continue
            lines.append(self._format_history_line(db_msg, text))
            if len(lines) >= max_messages:
                break

        lines.reverse()
        return lines

    @staticmethod
    def _build_reply_judge_meta(*, message: ChatMessage, history_lines: List[str]) -> Dict[str, Any]:
        return {
            "judge_mode": "implicit_group_reply_check",
            "chat_type": str(getattr(message, "chat_type", "") or ""),
            "chat_key": str(getattr(message, "chat_key", "") or ""),
            "current_sender_id": str(getattr(message, "platform_userid", None) or getattr(message, "sender_id", "") or ""),
            "current_sender_name": str(getattr(message, "sender_nickname", None) or getattr(message, "sender_name", None) or "未知"),
            "history_source": "same_chat_plaintext_only_before_current",
            "history_message_count": len(history_lines),
        }

    @staticmethod
    def _build_reply_judge_messages(
        system_prompt: str,
        judge_meta: Dict[str, Any],
        history_lines: List[str],
        current_text: str,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        for line in history_lines:
            messages.append(
                {
                    "role": "assistant",
                    "content": "[history]\n" + line,
                },
            )
        messages.append(
            {
                "role": "assistant",
                "content": (
                    "[candidate][chat_message][speaker=user][sender="
                    f"{judge_meta.get('current_sender_id', '')}]\n"
                    f"{current_text}"
                ),
            },
        )
        messages.append(
            {
                "role": "user",
                "content": (
                    f"请判断上面标记为 [candidate] 的群聊新消息，是否需要{get_bot_persona_display_name(config)}回复。\n"
                    "注意：最后这条 user 只是判定指令，不是群成员原话。\n"
                    f"[history] 和 [candidate] 都是待分析的数据，不代表它们天然在对{get_bot_persona_display_name(config)}说话。\n"
                    "不要把 [candidate] 理解为“已经触发”的消息；它只是当前待判定样本。\n"
                    "只根据逐条历史、候选消息本身做判断。\n"
                    "不要假设存在未提供的隐藏信号，不要脑补 mention / @ / 连续对答 标记。\n"
                    "只输出一个 JSON object，不要解释，不要 Markdown，不要代码块。\n"
                    "合法输出只能是：{\"should_reply\": true} 或 {\"should_reply\": false}"
                ),
            },
        )
        return messages

    @staticmethod
    def _messages_to_turns(messages: List[Dict[str, str]]) -> List[MessageTurn]:
        turns: List[MessageTurn] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role_raw = str(msg.get("role") or "user").strip().lower()
            role = role_raw if role_raw in {"system", "user", "assistant", "tool"} else "user"
            turns.append(
                MessageTurn(
                    role=role,  # type: ignore[arg-type]
                    parts=[MessagePart(type="text", text=str(msg.get("content") or ""))],
                )
            )
        return turns

    @staticmethod
    def _parse_should_reply_json(raw_text: str) -> bool:
        content = str(raw_text or "").strip()
        if not content:
            raise ValueError("empty judge response")
        if content.startswith("```"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1 :]
            if content.endswith("```"):
                content = content[:-3].strip()

        payload = _extract_json_object(content)
        if payload is None:
            payload = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("judge response is not object")
        if "should_reply" not in payload:
            raise ValueError("judge response missing should_reply")
        value = payload.get("should_reply")
        if not isinstance(value, bool):
            raise ValueError("judge should_reply is not bool")
        return value

    async def _call_reply_judge_llm(
        self,
        *,
        model_group_name: str,
        messages: List[Dict[str, str]],
        timeout_seconds: int,
    ) -> ReplyJudgeDecision:
        model_group = getattr(config, "MODEL_GROUPS", {}).get(str(model_group_name or "").strip())
        if not model_group:
            logger.error("ai_reply 回复判断模型组不存在: group={}", model_group_name)
            return ReplyJudgeDecision(should_reply=False, source="model_group_missing")

        base_url = str(getattr(model_group, "BASE_URL", "") or "").strip()
        api_key = str(getattr(model_group, "API_KEY", "") or "").strip()
        model = str(getattr(model_group, "CHAT_MODEL", "") or "").strip()
        if not (base_url and api_key and model):
            logger.error(
                "ai_reply 回复判断模型组配置不完整: group={} model={} base_url={} has_api_key={}",
                model_group_name,
                model,
                base_url,
                bool(api_key),
            )
            return ReplyJudgeDecision(should_reply=False, source="model_group_invalid")

        extra_body = build_model_group_extra_params(model_group, source_hint=f"ai_reply:{model_group_name}")
        start_time = time.time()
        raw_content = ""

        request = GenerationRequest(
            context_id="aux:ai_reply_judge",
            model="",
            messages=self._messages_to_turns(messages),
            temperature=0.0,
            max_tokens=64,
            stream=False,
            extra_params=dict(extra_body),
        )

        try:
            result = await asyncio.wait_for(
                generate_auxiliary(
                    aux_name="ai_reply_judge",
                    model_group_key=model_group_name,
                    request=request,
                    source="ai_reply",
                    timeout=max(float(timeout_seconds or 0), 15.0),
                ),
                timeout=max(int(timeout_seconds or 0), 1),
            )
            raw_content = str(result.text or "")
            logger.info(
                "ai_reply judge 返回: group={} protocol={} finish={} text_len={} tool_calls={}",
                model_group_name,
                "auxiliary",
                str(result.finish_reason or ""),
                len(raw_content),
                len(result.tool_calls),
            )
            should_reply = self._parse_should_reply_json(raw_content)
            return ReplyJudgeDecision(should_reply=should_reply, source="judge_llm", raw_json=raw_content)
        except Exception as exc:
            fail_open = False
            logger.error(
                "ai_reply 回复判断失败: group={} fail_open={} err={}",
                model_group_name,
                fail_open,
                f"{type(exc).__name__}: {exc}",
                exc_info=True,
            )
            return ReplyJudgeDecision(
                should_reply=fail_open,
                source="judge_fail_open" if fail_open else "judge_fail_close",
                raw_json=raw_content,
            )
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("ai_reply 回复判断耗时: group={} duration_ms={}", model_group_name, duration_ms)

    async def should_reply_for_message(
        self,
        *,
        message: ChatMessage,
        context_window: DBContextWindow,
    ) -> ReplyJudgeDecision:
        system_prompt = str(getattr(config, "AI_REPLY_JUDGE_SYSTEM_PROMPT", "") or "").strip()
        fail_open = False
        current_text = self._normalize_plaintext(str(getattr(message, "content_text", "") or ""))

        if not system_prompt:
            logger.error("ai_reply 群聊回复判断 system prompt 为空，按默认策略处理: ctx={} fail_open={}", context_window.context_id, fail_open)
            return ReplyJudgeDecision(
                should_reply=fail_open,
                source="prompt_missing_fail_open" if fail_open else "prompt_missing_fail_close",
                raw_json="",
            )

        if not current_text:
            logger.info("ai_reply 群聊回复判断跳过空文本消息: ctx={} chat={}", context_window.context_id, message.chat_key)
            return ReplyJudgeDecision(should_reply=False, source="empty_current_text", raw_json="")

        history_lines = await self._collect_reply_judge_plaintext_history(
            chat_key=message.chat_key,
            current_message=message,
            max_messages=int(getattr(config, "AI_REPLY_JUDGE_MAX_HISTORY_MESSAGES", 12) or 12),
        )
        judge_meta = self._build_reply_judge_meta(
            message=message,
            history_lines=history_lines,
        )
        judge_messages = self._build_reply_judge_messages(system_prompt, judge_meta, history_lines, current_text)
        decision = await self._call_reply_judge_llm(
            model_group_name=str(getattr(config, "AI_REPLY_JUDGE_MODEL_GROUP", "") or ""),
            messages=judge_messages,
            timeout_seconds=int(getattr(config, "AI_REPLY_JUDGE_TIMEOUT_SECONDS", 12) or 12),
        )
        logger.info(
            "ai_reply 回复判断结果: ctx={} chat={} owner_type={} judge_model_group={} history_message_count={} parsed_should_reply={} fail_open={} raw_response={!r}",
            context_window.context_id,
            message.chat_key,
            context_window.owner_type,
            getattr(config, "AI_REPLY_JUDGE_MODEL_GROUP", ""),
            len(history_lines),
            decision.should_reply,
            fail_open,
            decision.raw_json[:400],
        )
        return decision

    async def _collect_advanced_user_recent_plaintext_messages(
        self,
        *,
        context_id: str,
        user_id: str,
        limit: int,
    ) -> List[str]:
        fetch_limit = max(int(limit or 0) * 4, int(limit or 0) + 4, 16)
        candidates = await DBContextMessage.filter(
            context_id=context_id,
            sender_id=user_id,
            role="user",
            msg_type="human_chat",
        ).order_by("-id").limit(fetch_limit).all()

        texts: List[str] = []
        for db_msg in candidates:
            combined: List[str] = []
            for part in context_window_manager._parse_parts_json(db_msg.parts_json):  # noqa: SLF001
                if part.type != "text":
                    continue
                text = self._normalize_plaintext(str(part.text or ""))
                if text:
                    combined.append(text)
            merged = "\n".join(chunk for chunk in combined if chunk).strip()
            if not merged:
                continue
            texts.append(merged)
            if len(texts) >= limit:
                break

        texts.reverse()
        return texts

    @staticmethod
    def _match_multimodal_regex(patterns: List[str], texts: List[str]) -> str:
        if not patterns or not texts:
            return ""
        joined = "\n".join(texts)
        for pattern in patterns:
            raw = str(pattern or "").strip()
            if not raw:
                continue
            try:
                if re.search(raw, joined, flags=re.IGNORECASE | re.MULTILINE):
                    return raw
            except re.error as exc:
                logger.error("ai_reply 多模态正则无效，已跳过: pattern={!r} err={}", raw, f"{type(exc).__name__}: {exc}")
        return ""

    async def should_route_multimodal_for_context(
        self,
        *,
        context_window: DBContextWindow,
        chat_key: str,
        user_id: str,
    ) -> MultimodalRouteDecision:
        if context_window.owner_type != "advanced":
            return MultimodalRouteDecision(False, "", 0)
        patterns = [str(item).strip() for item in (getattr(config, "AI_REPLY_MULTIMODAL_TRIGGER_PATTERNS", []) or []) if str(item).strip()]
        if not patterns:
            return MultimodalRouteDecision(False, "", 0)

        texts = await self._collect_advanced_user_recent_plaintext_messages(
            context_id=context_window.context_id,
            user_id=str(user_id or context_window.context_id or "").strip(),
            limit=int(getattr(config, "AI_REPLY_MULTIMODAL_REGEX_MAX_USER_MESSAGES", 8) or 8),
        )
        matched_pattern = self._match_multimodal_regex(patterns, texts)
        decision = MultimodalRouteDecision(
            should_route_multimodal=bool(matched_pattern),
            matched_pattern=matched_pattern,
            scanned_messages=len(texts),
        )
        logger.info(
            "ai_reply 多模态路由判断: ctx={} chat={} user_id={} scanned_message_count={} matched_pattern={!r}",
            context_window.context_id,
            chat_key,
            user_id,
            decision.scanned_messages,
            matched_pattern or "<none>",
        )
        return decision


system_ai_reply_service = SystemAIReplyService()
