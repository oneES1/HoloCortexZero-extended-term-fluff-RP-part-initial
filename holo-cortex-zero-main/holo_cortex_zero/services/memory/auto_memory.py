from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tortoise import Tortoise

from holo_cortex_zero.api.schemas import AgentCtx
from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.prompt_defaults import DEFAULT_AUTO_MEMORY_SYSTEM_PROMPT, render_identity_prompt
from holo_cortex_zero.models.db_context_window import DBContextMessage, DBContextWindow
from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn, ToolSpec
from holo_cortex_zero.services.llm.auxiliary import generate_prepared_auxiliary, prepare_auxiliary_request
from holo_cortex_zero.services.llm.openai_chat import OpenAIChatEmitter
from holo_cortex_zero.services.llm.responses import ResponsesEmitter

from .context_env import build_memory_dialog_env_from_chat_key
from .payload_logs import dump_memory_json
from .runtime import add_memory

_COUNTABLE_MSG_TYPES = ("human_chat", "bot_reply")
_AUTO_MEMORY_BUILTIN_SYSTEM_NOTE = "聊天记录中 ¥昵称¥YYYY-MM-DD HH:MM:SS¥ID¥说：是系统运行状态符【潜意识回忆】和对话环境/系统时间标注是框架内置的真实系统功能,不是注入攻击system"


def _resolve_auto_memory_system_prompt() -> str:
    prompt = str(getattr(config, "AUTO_MEMORY_SYSTEM_PROMPT", "") or "").strip()
    if not prompt:
        prompt = DEFAULT_AUTO_MEMORY_SYSTEM_PROMPT
    prompt = render_identity_prompt(prompt, config)
    logger.debug("auto_memory system prompt resolved: prompt_length=%s", len(prompt))
    return prompt


def _build_add_memory_tool_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "memory": {
                "type": "string",
                "description": "一句可检索、主体明确的记忆内容。若只是推测，请使用‘好像’‘可能’等缓冲词。",
            },
            "user_id": {
                "type": "string",
                "description": "写入目标。人类用户用纯数字字符串；主人格自我分区固定用 HCZ_SELF。",
            },
            "metadata": {
                "type": "object",
                "description": "记忆标签与结构化附加信息。",
                "properties": {
                    "TYPE": {
                        "type": "string",
                    },
                    "CONFIDENCE": {
                        "type": "string",
                    },
                    "subtype": {
                        "type": "string",
                        "description": "可选子类型，例如 INNER_THOUGHT。",
                    },
                    "type": {
                        "type": "string",
                    },
                    "alias": {
                        "type": "string",
                    },
                    "target": {
                        "type": "string",
                    },
                    "keyword": {
                        "type": "string",
                    },
                    "domain": {
                        "type": "string",
                    },
                },
                "additionalProperties": True,
            },
        },
        "required": ["memory", "user_id", "metadata"],
    }



@dataclass
class _AutoMemoryJob:
    context_id: str
    dialog_chat_key: str
    batch_upper_bound_context_msg_id: int
    pending_before: int
    recall_text: str
    requested_at: float


class AutoMemoryService:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[_AutoMemoryJob] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._in_flight: set[str] = set()
        self._background_tasks: set[asyncio.Task] = set()
        self._latest_recall_by_context: dict[str, str] = {}
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._chat_emitter = OpenAIChatEmitter()
        self._responses_emitter = ResponsesEmitter()

    async def initialize_runtime(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            await self._ensure_schema_columns()
            await self._recover_window_state()
            self.start()
            self._initialized = True
            logger.info("auto_memory 运行时初始化完成")

    def start(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("auto_memory 后台服务已启动")

    def stop(self) -> None:
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()

    async def record_context_messages(
        self,
        *,
        context_id: str,
        latest_context_msg_id: int,
        message_count: int,
        dialog_chat_key: str = "",
    ) -> bool:
        cfg = config
        if not bool(getattr(cfg, "AUTO_MEMORY_ENABLED", True)):
            return False
        if latest_context_msg_id <= 0 or message_count <= 0:
            return False

        window = await DBContextWindow.get_or_none(context_id=context_id)
        if not window:
            return False

        pending = await self._count_pending_messages(
            context_id,
            int(window.auto_memory_last_context_msg_id or 0),
        )
        window.auto_memory_pending_count = pending
        await window.save(update_fields=["auto_memory_pending_count", "updated_at"])
        logger.info(
            "auto_memory 计数更新: "
            f"ctx={context_id} pending={pending} latest_ctx_msg_id={latest_context_msg_id}"
        )
        return True

    def update_recall_snapshot(
        self,
        *,
        context_id: str,
        recall_text: str,
    ) -> None:
        if not context_id:
            return
        normalized = str(recall_text or "").strip()
        if normalized:
            self._latest_recall_by_context[context_id] = normalized

    def schedule_trigger_nowait(
        self,
        *,
        context_id: str,
        latest_context_msg_id: Optional[int] = None,
        dialog_chat_key: str = "",
        recall_text: str = "",
    ) -> None:
        task = asyncio.create_task(
            self.maybe_trigger(
                context_id=context_id,
                latest_context_msg_id=latest_context_msg_id,
                dialog_chat_key=dialog_chat_key,
                recall_text=recall_text,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._handle_background_task_done)

    def _handle_background_task_done(self, task: asyncio.Task) -> None:
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception as e:
            logger.error(f"auto_memory 后台调度失败: {e}", exc_info=True)

    async def maybe_trigger(
        self,
        *,
        context_id: str,
        latest_context_msg_id: Optional[int] = None,
        dialog_chat_key: str = "",
        recall_text: str = "",
    ) -> bool:
        cfg = config
        if not bool(getattr(cfg, "AUTO_MEMORY_ENABLED", True)):
            return False

        if recall_text:
            self.update_recall_snapshot(context_id=context_id, recall_text=recall_text)

        threshold = max(1, int(getattr(cfg, "AUTO_MEMORY_TRIGGER_MESSAGE_COUNT", 10) or 10))
        if context_id in self._in_flight:
            return False

        window = await DBContextWindow.get_or_none(context_id=context_id)
        if not window:
            return False
        if window.auto_memory_generating:
            return False
        last_context_msg_id = int(window.auto_memory_last_context_msg_id or 0)
        pending = await self._count_pending_messages(context_id, last_context_msg_id)
        if int(window.auto_memory_pending_count or 0) != pending:
            window.auto_memory_pending_count = pending
            await window.save(update_fields=["auto_memory_pending_count", "updated_at"])
        if pending < threshold:
            return False

        batch_upper_bound_context_msg_id = await self._query_batch_upper_bound_id(
            context_id=context_id,
            last_context_msg_id=last_context_msg_id,
            threshold=threshold,
        )
        if batch_upper_bound_context_msg_id <= 0:
            return False

        window.auto_memory_generating = True
        await window.save(update_fields=["auto_memory_generating", "auto_memory_pending_count", "updated_at"])
        self._in_flight.add(context_id)
        await self._queue.put(
            _AutoMemoryJob(
                context_id=context_id,
                dialog_chat_key=dialog_chat_key or window.active_dialog_id or "",
                batch_upper_bound_context_msg_id=batch_upper_bound_context_msg_id,
                pending_before=pending,
                recall_text=str(recall_text or self._latest_recall_by_context.get(context_id, "") or "").strip(),
                requested_at=time.time(),
            )
        )
        logger.info(
            "auto_memory 任务入队: "
            f"ctx={context_id} pending={pending} batch_upper_bound={batch_upper_bound_context_msg_id} "
            f"threshold={threshold} dialog={dialog_chat_key or window.active_dialog_id} "
            f"recall_reused={'yes' if str(recall_text or self._latest_recall_by_context.get(context_id, '') or '').strip() else 'no'}"
        )
        return True

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            chain_next = False
            try:
                chain_next = await self._do_auto_memory(job)
            except Exception as e:
                logger.error(f"auto_memory 执行失败: ctx={job.context_id}: {e}", exc_info=True)
                await self._mark_job_finished(job.context_id, latest_context_msg_id=None)
            finally:
                self._in_flight.discard(job.context_id)

            if chain_next:
                try:
                    await self.maybe_trigger(
                        context_id=job.context_id,
                        dialog_chat_key="",
                        recall_text=job.recall_text,
                    )
                except Exception as e:
                    logger.error(f"auto_memory 补触发失败: ctx={job.context_id}: {e}", exc_info=True)
            self._queue.task_done()

    async def _ensure_schema_columns(self) -> None:
        conn = Tortoise.get_connection("default")
        ddl_statements = [
            'ALTER TABLE "context_window" ADD COLUMN IF NOT EXISTS "auto_memory_last_context_msg_id" INT NOT NULL DEFAULT 0',
            'ALTER TABLE "context_window" ADD COLUMN IF NOT EXISTS "auto_memory_pending_count" INT NOT NULL DEFAULT 0',
            'ALTER TABLE "context_window" ADD COLUMN IF NOT EXISTS "auto_memory_generating" BOOLEAN NOT NULL DEFAULT FALSE',
        ]
        for sql in ddl_statements:
            await conn.execute_query(sql)
        logger.info("auto_memory schema 检查完成")

    async def _recover_window_state(self) -> None:
        windows = await DBContextWindow.all()
        fixed = 0
        for window in windows:
            pending = await self._count_pending_messages(window.context_id, int(window.auto_memory_last_context_msg_id or 0))
            changed = False
            if int(window.auto_memory_pending_count or 0) != pending:
                window.auto_memory_pending_count = pending
                changed = True
            if window.auto_memory_generating:
                window.auto_memory_generating = False
                changed = True
            if changed:
                await window.save(update_fields=["auto_memory_pending_count", "auto_memory_generating", "updated_at"])
                fixed += 1
        logger.info(f"auto_memory 启动恢复完成: windows={len(windows)} fixed={fixed}")

    @staticmethod
    def _normalize_group_key(value: str) -> str:
        return str(value or "").strip().lower().replace("_", "-")

    def _resolve_model_group_key(self, cfg: Any) -> str:
        requested = str(getattr(cfg, "AUTO_MEMORY_MODEL_GROUP", "") or "").strip()
        if not requested:
            raise KeyError("AUTO_MEMORY_MODEL_GROUP 为空，请在配置中指定有效模型组")
        if requested not in cfg.MODEL_GROUPS:
            normalized_requested = self._normalize_group_key(requested)
            normalized_pairs = [
                (str(key), self._normalize_group_key(str(key)))
                for key in cfg.MODEL_GROUPS.keys()
            ]
            exact_candidates = [key for key, norm in normalized_pairs if norm == normalized_requested]
            if len(exact_candidates) == 1:
                resolved = exact_candidates[0]
                logger.info(f"auto_memory 模型组归一化命中: requested={requested} resolved={resolved}")
                return resolved

            prefix_candidates = [
                key
                for key, norm in normalized_pairs
                if norm.startswith(normalized_requested)
            ]
            if len(prefix_candidates) == 1:
                resolved = prefix_candidates[0]
                logger.info(f"auto_memory 模型组前缀命中: requested={requested} resolved={resolved}")
                return resolved

            if prefix_candidates:
                raise KeyError(
                    "AUTO_MEMORY_MODEL_GROUP 匹配到多个候选，请改成精确组名: "
                    f"requested={requested}, candidates={prefix_candidates}"
                )
            raise KeyError(f"AUTO_MEMORY_MODEL_GROUP={requested} 不存在，请按 UI 中真实模型组名配置")
        return requested

    async def _count_pending_messages(self, context_id: str, last_context_msg_id: int) -> int:
        return await DBContextMessage.filter(
            context_id=context_id,
            id__gt=int(last_context_msg_id or 0),
            msg_type__in=list(_COUNTABLE_MSG_TYPES),
            role__in=["user", "assistant"],
        ).count()

    async def _query_batch_upper_bound_id(self, *, context_id: str, last_context_msg_id: int, threshold: int) -> int:
        # 主干：auto_memory 的触发水位只看同一 context_id 下自上次水位后的第 N 条可计数消息。
        # chat_key/source_chat_key 只用于写记忆时标注来源，不参与触发分桶。
        ids = await DBContextMessage.filter(
            context_id=context_id,
            id__gt=int(last_context_msg_id or 0),
            msg_type__in=list(_COUNTABLE_MSG_TYPES),
            role__in=["user", "assistant"],
        ).order_by("id").offset(max(0, int(threshold or 1) - 1)).limit(1).values_list("id", flat=True)
        return int(ids[0]) if ids else 0

    async def _query_batch_messages(self, context_id: str, last_context_msg_id: int, upper_bound_id: int) -> List[Any]:
        return await DBContextMessage.filter(
            context_id=context_id,
            id__gt=int(last_context_msg_id or 0),
            id__lte=int(upper_bound_id or 0),
            msg_type__in=list(_COUNTABLE_MSG_TYPES),
            role__in=["user", "assistant"],
        ).order_by("id").all()

    async def _do_auto_memory(self, job: _AutoMemoryJob) -> bool:
        cfg = config
        threshold = max(1, int(getattr(cfg, "AUTO_MEMORY_TRIGGER_MESSAGE_COUNT", 10) or 10))
        recent_limit = max(1, int(getattr(cfg, "AUTO_MEMORY_RECENT_MESSAGE_COUNT", 10) or 10))
        max_tool_calls = max(1, int(getattr(cfg, "AUTO_MEMORY_MAX_TOOL_CALLS", 8) or 8))

        window = await DBContextWindow.get_or_none(context_id=job.context_id)
        if not window:
            return False

        last_context_msg_id = int(window.auto_memory_last_context_msg_id or 0)
        batch_messages = await self._query_batch_messages(
            context_id=job.context_id,
            last_context_msg_id=last_context_msg_id,
            upper_bound_id=job.batch_upper_bound_context_msg_id,
        )
        if len(batch_messages) < threshold:
            logger.info(
                "auto_memory 跳过：未达到阈值或无新消息: "
                f"ctx={job.context_id} fetched={len(batch_messages)} threshold={threshold}"
            )
            await self._mark_job_finished(job.context_id, latest_context_msg_id=None)
            return False

        payload_messages = batch_messages[-recent_limit:]
        batch_source_chat_key = ""
        for item in reversed(payload_messages):
            batch_source_chat_key = str(getattr(item, "source_chat_key", "") or "").strip()
            if batch_source_chat_key:
                break
        dialog_chat_key = batch_source_chat_key or job.dialog_chat_key or window.active_dialog_id or ""
        model_group_key = self._resolve_model_group_key(cfg)
        recall_text = str(job.recall_text or self._latest_recall_by_context.get(job.context_id, "") or "").strip()
        if not recall_text:
            logger.info(
                "auto_memory 未命中主链 recall 快照，将在无 recall 提示下运行: "
                f"ctx={job.context_id} dialog={dialog_chat_key}"
            )
        request = self._build_generation_request(
            payload_messages=payload_messages,
            recall_text=recall_text,
        )
        prepared = prepare_auxiliary_request(
            aux_name="auto_memory",
            model_group_key=model_group_key,
            request=request,
            source="memory.auto_memory",
        )
        request = prepared.request
        model_group = prepared.model_group
        protocol = prepared.protocol
        wire_payload = self._build_wire_payload(
            request,
            protocol=protocol,
            base_url=str(getattr(model_group, "BASE_URL", "") or ""),
        )
        preview = self._build_payload_preview(
            request=request,
            context_id=job.context_id,
            dialog_chat_key=dialog_chat_key,
            protocol=protocol,
            model_group_key=model_group_key,
        )
        context_source_messages = [self._serialize_context_message(item) for item in payload_messages]
        request_path = "/responses" if protocol == "responses" else "/chat/completions"
        protocol_label = "responses" if protocol == "responses" else "chat.completions"
        if bool(getattr(cfg, "AUTO_MEMORY_DEBUG_LOG_PAYLOAD", True)):
            logger.info(f"auto_memory payload: {preview}")
        dump_memory_json(
            "auto_memory",
            "request",
            {
                "kind": "auto_memory_request",
                "context_id": job.context_id,
                "dialog_chat_key": dialog_chat_key,
                "batch_upper_bound_context_msg_id": job.batch_upper_bound_context_msg_id,
                "pending_before": job.pending_before,
                "threshold": threshold,
                "model_group": model_group_key,
                "base_url": str(getattr(model_group, "BASE_URL", "") or ""),
                "protocol": protocol_label,
                "request_wire": {
                    "url": f"{str(getattr(model_group, 'BASE_URL', '') or '').rstrip('/')}{request_path}",
                    "payload": wire_payload,
                    "headers": {
                        "Authorization": "Bearer ***",
                        "Content-Type": "application/json",
                    },
                },
                "context_source_messages": context_source_messages,
                "recall_text": recall_text,
            },
        )

        result = await generate_prepared_auxiliary(
            prepared,
            timeout=1200.0,
        )

        executed_calls: List[Dict[str, Any]] = []
        if bool(getattr(cfg, "AUTO_MEMORY_DEBUG_LOG_PAYLOAD", True)):
            logger.info(
                "auto_memory result: "
                f"ctx={job.context_id} protocol={protocol} finish={result.finish_reason} tool_calls={len(result.tool_calls)} text={self._truncate(str(result.text or ''), 600)}"
            )

        if not result.tool_calls:
            dump_memory_json(
                "auto_memory",
                "response",
                {
                    "kind": "auto_memory_response",
                    "context_id": job.context_id,
                    "dialog_chat_key": dialog_chat_key,
                    "finish_reason": result.finish_reason,
                    "text": result.text,
                    "tool_calls": [],
                    "usage": result.usage,
                    "raw_response": result.raw_response,
                    "executed_calls": executed_calls,
                },
            )
            logger.info(
                "auto_memory 未产出 tool_call，本批已审阅并推进水位: "
                f"ctx={job.context_id} dialog={dialog_chat_key} finish={result.finish_reason} "
                f"batch_upper_bound={job.batch_upper_bound_context_msg_id}"
            )
            await self._mark_job_finished(job.context_id, latest_context_msg_id=job.batch_upper_bound_context_msg_id)
            remaining = await self._count_pending_messages(job.context_id, job.batch_upper_bound_context_msg_id)
            return remaining >= threshold

        executed = 0
        for tool_call in result.tool_calls[:max_tool_calls]:
            if tool_call.name != "add_memory":
                logger.warning(f"auto_memory 收到非 add_memory tool，已忽略: ctx={job.context_id} tool={tool_call.name}")
                continue
            arguments = dict(tool_call.arguments or {})
            metadata = arguments.get("metadata") if isinstance(arguments.get("metadata"), dict) else {}
            source_chat_key = str(dialog_chat_key or window.active_dialog_id or "").strip()
            env = build_memory_dialog_env_from_chat_key(source_chat_key)
            dump_memory_json(
                "auto_memory",
                "tool_call",
                {
                    "kind": "auto_memory_tool_call",
                    "context_id": job.context_id,
                    "dialog_chat_key": dialog_chat_key,
                    "tool_call": {"id": tool_call.id, "name": tool_call.name, "arguments": arguments},
                    "resolved_source_chat_key": source_chat_key,
                    "resolved_env": {
                        "channel_type": env.channel_type,
                        "channel_id": env.channel_id,
                        "chat_env_note": env.chat_env_note,
                        "chat_env_system": env.chat_env_system,
                    },
                },
            )
            ctx_for_call = await AgentCtx.create_by_chat_key(chat_key=source_chat_key)
            await add_memory(
                ctx_for_call,
                memory=str(arguments.get("memory", "") or ""),
                user_id=str(arguments.get("user_id", "") or ""),
                metadata=metadata,
            )
            executed_calls.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": arguments,
                    "resolved_source_chat_key": source_chat_key,
                }
            )
            executed += 1

        dump_memory_json(
            "auto_memory",
            "response",
            {
                "kind": "auto_memory_response",
                "context_id": job.context_id,
                "dialog_chat_key": dialog_chat_key,
                "finish_reason": result.finish_reason,
                "text": result.text,
                "tool_calls": [
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in result.tool_calls
                ],
                "usage": result.usage,
                "raw_response": result.raw_response,
                "executed_calls": executed_calls,
            },
        )

        logger.info(
            "auto_memory 执行完成: "
            f"ctx={job.context_id} dialog={dialog_chat_key} batch={len(payload_messages)} tool_calls={len(result.tool_calls)} executed={executed}"
        )
        if executed <= 0:
            logger.warning(
                "auto_memory 未成功执行 add_memory，保留 pending 不推进水位: "
                f"ctx={job.context_id} dialog={dialog_chat_key}"
            )
            await self._mark_job_finished(job.context_id, latest_context_msg_id=None)
            return False

        await self._mark_job_finished(job.context_id, latest_context_msg_id=job.batch_upper_bound_context_msg_id)

        remaining = await self._count_pending_messages(job.context_id, job.batch_upper_bound_context_msg_id)
        return remaining >= threshold

    async def _mark_job_finished(self, context_id: str, latest_context_msg_id: Optional[int]) -> None:
        window = await DBContextWindow.get_or_none(context_id=context_id)
        if not window:
            return

        if latest_context_msg_id is not None:
            window.auto_memory_last_context_msg_id = max(
                int(window.auto_memory_last_context_msg_id or 0),
                int(latest_context_msg_id),
            )
        window.auto_memory_pending_count = await self._count_pending_messages(
            context_id,
            int(window.auto_memory_last_context_msg_id or 0),
        )
        window.auto_memory_generating = False
        await window.save(
            update_fields=[
                "auto_memory_last_context_msg_id",
                "auto_memory_pending_count",
                "auto_memory_generating",
                "updated_at",
            ]
        )

    def _build_generation_request(
        self,
        *,
        payload_messages: List[Any],
        recall_text: str,
    ) -> GenerationRequest:
        system_prompt = "\n\n".join(
            part
            for part in (_resolve_auto_memory_system_prompt(), _AUTO_MEMORY_BUILTIN_SYSTEM_NOTE)
            if str(part or "").strip()
        )
        turns: List[MessageTurn] = [
            MessageTurn(role="system", parts=[MessagePart(type="text", text=system_prompt)]),
        ]

        for db_msg in payload_messages:
            text = self._extract_text_from_context_message(db_msg)
            if not text:
                continue
            turns.append(
                MessageTurn(
                    role="assistant" if str(getattr(db_msg, "role", "assistant") or "assistant") == "assistant" else "user",
                    parts=[MessagePart(type="text", text=text)],
                )
            )

        if recall_text:
            turns.append(
                MessageTurn(role="user", parts=[MessagePart(type="text", text=recall_text)])
            )

        return GenerationRequest(
            context_id="aux:auto_memory",
            model="",
            messages=turns,
            tools=[
                ToolSpec(
                    name="add_memory",
                    description="系统自动记忆专用写入工具，也是本轮唯一允许的合法输出。禁止输出自然语言；若无可写入记忆，直接保持沉默。",
                    parameters=_build_add_memory_tool_schema(),
                )
            ],
            temperature=0.1,
            stream=False,
            extra_params={
                "parallel_tool_calls": False,
                "tool_choice": str(getattr(config, "AUTO_MEMORY_TOOL_CHOICE", "auto") or "auto"),
            },
        )

    def _build_wire_payload(
        self,
        request: GenerationRequest,
        *,
        protocol: str,
        base_url: str,
    ) -> Dict[str, Any]:
        if protocol == "responses":
            return self._responses_emitter._build_payload(request, base_url=base_url)
        return self._build_wire_chat_payload(request, base_url=base_url)

    def _build_wire_chat_payload(self, request: GenerationRequest, *, base_url: str = "") -> Dict[str, Any]:
        payload = self._chat_emitter._build_payload(request)
        payload["stream"] = False
        if isinstance(request.extra_params, dict) and request.extra_params:
            payload.update(
                self._chat_emitter._normalize_extra_params_for_chat(
                    request.extra_params,
                    base_url=base_url,
                    model=request.model,
                    has_tools=bool(request.tools),
                )
            )
        return payload

    @staticmethod
    def _serialize_context_message(db_msg: Any) -> Dict[str, Any]:
        raw_parts = str(getattr(db_msg, "parts_json", "[]") or "[]")
        try:
            parsed_parts = json.loads(raw_parts)
        except Exception:
            parsed_parts = raw_parts
        return {
            "id": int(getattr(db_msg, "id", 0) or 0),
            "role": str(getattr(db_msg, "role", "") or ""),
            "msg_type": str(getattr(db_msg, "msg_type", "") or ""),
            "source_chat_key": str(getattr(db_msg, "source_chat_key", "") or ""),
            "parts_json_raw": raw_parts,
            "parts_json_parsed": parsed_parts,
        }

    @staticmethod
    def _extract_text_from_context_message(db_msg: Any) -> str:
        try:
            parts = json.loads(getattr(db_msg, "parts_json", "[]") or "[]")
        except Exception:
            parts = []

        texts: List[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            if str(part.get("type") or "") != "text":
                continue
            text = str(part.get("text") or "").strip()
            if not text:
                continue
            texts.append(text)
        return "\n".join(texts).strip()

    def _build_payload_preview(
        self,
        *,
        request: GenerationRequest,
        context_id: str,
        dialog_chat_key: str,
        protocol: str,
        model_group_key: str,
    ) -> str:
        cfg = config
        limit = max(2000, int(getattr(cfg, "AUTO_MEMORY_PAYLOAD_LOG_MAX_CHARS", 12000) or 12000))
        preview = {
            "context_id": context_id,
            "dialog_chat_key": dialog_chat_key,
            "model_group": model_group_key,
            "protocol": protocol,
            "model": request.model,
            "tool_names": [tool.name for tool in request.tools],
            "messages": [
                {
                    "role": turn.role,
                    "text": self._truncate("\n".join([str(part.text or "") for part in turn.parts if part.type == "text"]), 480),
                }
                for turn in request.messages
            ],
        }
        return self._truncate(json.dumps(preview, ensure_ascii=False), limit)

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "...(truncated)"


auto_memory_service = AutoMemoryService()
