from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from holo_cortex_zero.adapters.interface.schemas.platform import PlatformSendResponse
from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn
from holo_cortex_zero.services.context_window.manager import context_window_manager
from holo_cortex_zero.services.llm.auxiliary import generate_auxiliary


_AUX_NAME = "bot_backfill_cleanup"
_AUX_SOURCE = "bot_backfill_cleanup"
_CLEANUP_TIMEOUT_SECONDS = 50.0
_CLEANUP_MAX_CHARS = 45
_SYSTEM_PROMPT = (
    "你的任务是**将对话文本进行留白，不完整，人味化**，你收到一份待清理文本，"
    "你必须将其清理为45字内，要求：人类聊天发言语气，句子不完整无格式，可爱俏皮"
    "**删多余描写，删无实质性内容**，保留核心完整信息"
    "你**只能输出45字内清理后文段**，禁止输出无关额外内容"
)
_FINAL_USER_PROMPT = "现在你**只输出45字内清理后文段**"


@dataclass
class _PendingBotBackfill:
    key: str
    context_id: str
    text: str
    source_chat_key: str
    source_message_id: str
    reasoning_content: Optional[str]
    task: Optional[asyncio.Task[None]] = None
    flushed: bool = False


class BotBackfillCleanupService:
    def __init__(self) -> None:
        self._pending: dict[str, _PendingBotBackfill] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def is_enabled() -> bool:
        return bool(getattr(config, "BOT_MESSAGE_BACKFILL_CLEANUP_ENABLED", False))

    @staticmethod
    def _threshold_chars() -> int:
        return max(1, int(getattr(config, "BOT_MESSAGE_BACKFILL_CLEANUP_THRESHOLD_CHARS", 120) or 120))

    @staticmethod
    def _model_group_key() -> str:
        return str(getattr(config, "BOT_MESSAGE_BACKFILL_CLEANUP_MODEL_GROUP", "") or "").strip()

    @staticmethod
    def _normalize_source_message_id(
        *,
        plt_response: Optional[PlatformSendResponse],
        chat_message_db_id: int = 0,
    ) -> str:
        platform_id = str(getattr(plt_response, "message_id", "") or "").strip() if plt_response else ""
        if platform_id:
            return platform_id
        if chat_message_db_id > 0:
            return f"dbid_{chat_message_db_id}"
        return ""

    @staticmethod
    def _pending_key(context_id: str, source_message_id: str, source_chat_key: str) -> str:
        return "|".join([
            str(context_id or "").strip(),
            str(source_chat_key or "").strip(),
            str(source_message_id or "").strip(),
        ])

    @staticmethod
    def _collapse_and_limit_text(text: str) -> str:
        cleaned = context_window_manager._sanitize_bot_assistant_text(str(text or ""))
        cleaned = " ".join(cleaned.split()).strip()
        if len(cleaned) > _CLEANUP_MAX_CHARS:
            cleaned = cleaned[:_CLEANUP_MAX_CHARS].strip()
        return cleaned

    async def schedule_bot_reply_backfill(
        self,
        *,
        context_id: str,
        text: str,
        source_chat_key: str = "",
        plt_response: Optional[PlatformSendResponse] = None,
        chat_message_db_id: int = 0,
        reasoning_content: Optional[str] = None,
    ) -> None:
        source_message_id = self._normalize_source_message_id(
            plt_response=plt_response,
            chat_message_db_id=chat_message_db_id,
        )
        fallback_text = context_window_manager._sanitize_bot_assistant_text(str(text or ""))
        if not fallback_text:
            return

        threshold = self._threshold_chars()
        if not self.is_enabled() or len(fallback_text) <= threshold:
            await self._record_backfill(
                context_id=context_id,
                text=fallback_text,
                source_chat_key=source_chat_key,
                source_message_id=source_message_id,
                reasoning_content=reasoning_content,
            )
            return

        logger.info(
            "bot 回填清理已触发: chars=%s threshold=%s source_id_present=%s",
            len(fallback_text),
            threshold,
            bool(source_message_id),
        )

        model_group_key = self._model_group_key()
        if not model_group_key:
            await self._fallback_record(
                reason="model_group_missing",
                context_id=context_id,
                text=fallback_text,
                source_chat_key=source_chat_key,
                source_message_id=source_message_id,
                reasoning_content=reasoning_content,
            )
            return

        pending = _PendingBotBackfill(
            key=self._pending_key(context_id, source_message_id, source_chat_key),
            context_id=str(context_id or "").strip(),
            text=fallback_text,
            source_chat_key=str(source_chat_key or "").strip(),
            source_message_id=source_message_id,
            reasoning_content=reasoning_content,
        )
        async with self._lock:
            self._pending[pending.key] = pending
            pending.task = asyncio.create_task(self._run_cleanup(pending, model_group_key))

    async def flush_pending_for_context(self, context_id: str, *, reason: str) -> int:
        normalized_context_id = str(context_id or "").strip()
        if not normalized_context_id:
            return 0

        async with self._lock:
            pending_items = [
                item
                for item in self._pending.values()
                if item.context_id == normalized_context_id and not item.flushed
            ]
            for item in pending_items:
                item.flushed = True
                self._pending.pop(item.key, None)

        flushed = 0
        for item in pending_items:
            await self._fallback_record(
                reason=reason,
                context_id=item.context_id,
                text=item.text,
                source_chat_key=item.source_chat_key,
                source_message_id=item.source_message_id,
                reasoning_content=item.reasoning_content,
            )
            flushed += 1
        return flushed

    async def _run_cleanup(self, pending: _PendingBotBackfill, model_group_key: str) -> None:
        try:
            async with self._lock:
                current = self._pending.get(pending.key)
                if current is not pending or pending.flushed:
                    return

            result_text = await self._call_cleanup_llm(pending.text, model_group_key)
            cleaned_text = self._collapse_and_limit_text(result_text)
            if not cleaned_text:
                await self._fallback_record_pending(pending, "empty_result")
                return

            async with self._lock:
                current = self._pending.get(pending.key)
                if current is not pending or pending.flushed:
                    return
                self._pending.pop(pending.key, None)

            await self._record_backfill(
                context_id=pending.context_id,
                text=cleaned_text,
                source_chat_key=pending.source_chat_key,
                source_message_id=pending.source_message_id,
                reasoning_content=pending.reasoning_content,
            )
        except asyncio.TimeoutError:
            await self._fallback_record_pending(pending, "timeout")
        except Exception as exc:
            await self._fallback_record_pending(pending, type(exc).__name__)

    async def _call_cleanup_llm(self, text: str, model_group_key: str) -> str:
        request = GenerationRequest(
            context_id=f"aux:{_AUX_NAME}",
            model="",
            messages=[
                MessageTurn(role="system", parts=[MessagePart(type="text", text=_SYSTEM_PROMPT)]),
                MessageTurn(role="user", parts=[MessagePart(type="text", text=text)]),
                MessageTurn(role="user", parts=[MessagePart(type="text", text=_FINAL_USER_PROMPT)]),
            ],
            temperature=0.3,
            max_tokens=None,
            stream=False,
            cache_hints={"cache_domain": _AUX_NAME},
        )
        result = await asyncio.wait_for(
            generate_auxiliary(
                aux_name=_AUX_NAME,
                model_group_key=model_group_key,
                request=request,
                source=_AUX_SOURCE,
                timeout=_CLEANUP_TIMEOUT_SECONDS,
            ),
            timeout=_CLEANUP_TIMEOUT_SECONDS,
        )
        return str(result.text or "")

    async def _fallback_record_pending(self, pending: _PendingBotBackfill, reason: str) -> None:
        async with self._lock:
            current = self._pending.get(pending.key)
            if current is not pending or pending.flushed:
                return
            pending.flushed = True
            self._pending.pop(pending.key, None)

        await self._fallback_record(
            reason=reason,
            context_id=pending.context_id,
            text=pending.text,
            source_chat_key=pending.source_chat_key,
            source_message_id=pending.source_message_id,
            reasoning_content=pending.reasoning_content,
        )

    async def _fallback_record(
        self,
        *,
        reason: str,
        context_id: str,
        text: str,
        source_chat_key: str,
        source_message_id: str,
        reasoning_content: Optional[str],
    ) -> None:
        logger.warning(
            "bot 回填清理降级: reason=%s chars=%s source_id_present=%s",
            str(reason or "unknown"),
            len(str(text or "")),
            bool(source_message_id),
        )
        await self._record_backfill(
            context_id=context_id,
            text=text,
            source_chat_key=source_chat_key,
            source_message_id=source_message_id,
            reasoning_content=reasoning_content,
        )

    async def _record_backfill(
        self,
        *,
        context_id: str,
        text: str,
        source_chat_key: str,
        source_message_id: str,
        reasoning_content: Optional[str],
    ) -> None:
        if source_message_id:
            from holo_cortex_zero.models.db_context_window import DBContextMessage

            exists = await DBContextMessage.filter(
                context_id=context_id,
                source_message_id=source_message_id,
            ).exists()
            if exists:
                return

        await context_window_manager.record_bot_reply_backfill(
            context_id=context_id,
            text=text,
            source_chat_key=source_chat_key,
            source_message_id=source_message_id,
            reasoning_content=reasoning_content,
        )
        await context_window_manager.check_and_trigger_compress(context_id)


bot_backfill_cleanup_service = BotBackfillCleanupService()
