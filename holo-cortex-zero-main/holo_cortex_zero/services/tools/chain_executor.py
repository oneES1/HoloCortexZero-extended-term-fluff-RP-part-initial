"""Tool 链循环执行引擎

负责：
1. 组装上下文 → 调用 LLM → 解析返回
2. 纯文本 → 发送回复 → 结束
3. tool_calls → 逐个执行 → 结果加入历史 → 继续循环
4. 停机条件检查（max 迭代、连续空、超时、全挂）
5. 每循环更新历史（吸收新聊天消息）
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.models.db_context_window import DBContextWindow
from holo_cortex_zero.models.db_tool_chain_trace import DBToolChainTrace, ToolChainTraceStopType
from holo_cortex_zero.schemas.ir import (
    GenerationResult,
    MessagePart,
    MessageTurn,
    ToolCall,
    ToolResult,
)
from holo_cortex_zero.services.context_window.manager import context_window_manager
from holo_cortex_zero.services.llm.router import LLMAPIChainExhaustedError, llm_router
from holo_cortex_zero.services.tools.registry import RegisteredTool, ToolRuntimeBinding, tool_registry


class ToolChainExecutor:
    """Tool 链循环执行引擎"""

    # 清洗 LLM 输出中的 [id|name] 格式前缀
    _ID_NAME_PATTERN = re.compile(r'\[[\d]+\|[^\]]+\]\s*')
    # 清洗 LLM 输出中误模仿的 ¥ 系统运行状态符
    _SYS_MARKER_PATTERN = re.compile(
        r'(?:¥[^¥\n]*¥(?:\d{4}-\d{2}-\d{2}\s+)?\d{2}:\d{2}:\d{2}¥[^¥\n]*¥说：|(?:\d{4}-\d{2}-\d{2}\s+)?\d{2}:\d{2}:\d{2}¥[^¥\n]*¥[^¥\n]*¥说：)'
    )
    _THINK_TAG_PATTERN = re.compile(r'<think>.*?</think>', flags=re.DOTALL | re.IGNORECASE)
    _THINK_TAG_ONLY_PATTERN = re.compile(r'</?think>', flags=re.IGNORECASE)
    _UNEXECUTED_CONTROL_PLANE_PATTERN = re.compile(
        r'(?:【工具调用】|<tool_call>|<\|tool_call\|>|<\|tool_call>|<function=[^>]+>)',
        flags=re.IGNORECASE,
    )
    _CONTROL_PLANE_SNIPPET_PATTERN = re.compile(
        r'(?:【工具调用】[^\n]*|<tool_call>.*?</tool_call>|<\|tool_call\|>.*?(?:<\|/tool_call\|>|$)|<\|tool_call>.*?(?:<tool_call\|>|<\|/tool_call\|>|</tool_call>|$)|<function=[^>]+>.*?</function>)',
        flags=re.IGNORECASE | re.DOTALL,
    )

    def __init__(self) -> None:
        self.max_callbacks: int = 50
        self.total_timeout_seconds: float = 300.0
        self.consecutive_empty_limit: int = 3

    @staticmethod
    def _extract_model_name(result: GenerationResult, fallback_model: str) -> str:
        raw_response = result.raw_response
        if isinstance(raw_response, dict):
            for key in ("model", "model_name", "modelVersion"):
                value = raw_response.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            response_meta = raw_response.get("response")
            if isinstance(response_meta, dict):
                for key in ("model", "model_name", "modelVersion"):
                    value = response_meta.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

        return str(fallback_model or "").strip()

    @staticmethod
    def _extract_usage_metrics(usage: Optional[Dict[str, Any]]) -> Dict[str, int]:
        if not isinstance(usage, dict):
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}

        usage_metadata = usage.get("usageMetadata")
        nested_usage = usage_metadata if isinstance(usage_metadata, dict) else usage

        def pick_int(*keys: str) -> int:
            for key in keys:
                value = nested_usage.get(key)
                if isinstance(value, (int, float)):
                    return int(value)
            return 0

        prompt_tokens = pick_int("prompt_tokens", "input_tokens", "promptTokenCount", "inputTokenCount")
        prompt_cache_hit_tokens = pick_int("prompt_cache_hit_tokens", "promptCacheHitTokens")
        prompt_cache_miss_tokens = pick_int("prompt_cache_miss_tokens", "promptCacheMissTokens")
        prompt_details = nested_usage.get("prompt_tokens_details")
        input_details = nested_usage.get("input_tokens_details")
        cached_tokens = 0
        for details in (prompt_details, input_details):
            if not isinstance(details, dict):
                continue
            value = details.get("cached_tokens")
            if not isinstance(value, (int, float)):
                value = details.get("cachedTokens")
            if isinstance(value, (int, float)):
                cached_tokens = int(value)
                break
        if cached_tokens <= 0 and prompt_cache_hit_tokens > 0:
            cached_tokens = prompt_cache_hit_tokens
        if prompt_tokens <= 0 and (prompt_cache_hit_tokens > 0 or prompt_cache_miss_tokens > 0):
            prompt_tokens = prompt_cache_hit_tokens + prompt_cache_miss_tokens
        completion_tokens = pick_int(
            "completion_tokens",
            "output_tokens",
            "candidatesTokenCount",
            "outputTokenCount",
        )
        total_tokens = pick_int("total_tokens", "totalTokenCount")
        if total_tokens <= 0:
            total_tokens = prompt_tokens + completion_tokens

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
        }

    @staticmethod
    def _truncate_text(text: Any, limit: int = 12000) -> str:
        content = str(text or "")
        if len(content) <= limit:
            return content
        return f"{content[:limit]}\n...<truncated {len(content) - limit} chars>"

    @classmethod
    def _parts_to_preview(cls, parts: List[MessagePart]) -> str:
        chunks: List[str] = []
        for part in parts:
            if part.type == "text" and part.text:
                chunks.append(part.text)
                continue

            label = part.type.upper()
            if part.url:
                chunks.append(f"[{label}] {part.url}")
            else:
                chunks.append(f"[{label}]")

        return cls._truncate_text("\n".join(chunks).strip())

    @classmethod
    def _has_unexecuted_control_plane_text(cls, text: Optional[str]) -> bool:
        content = str(text or "").strip()
        if not content:
            return False
        return bool(cls._UNEXECUTED_CONTROL_PLANE_PATTERN.search(content))

    @classmethod
    def _sanitize_internal_error_text(cls, text: Any) -> str:
        content = str(text or "").strip()
        if not content:
            return "未知错误"
        content = cls._CONTROL_PLANE_SNIPPET_PATTERN.sub('[控制平面内容已隐藏]', content)
        content = cls._SYS_MARKER_PATTERN.sub('', content)
        content = cls._ID_NAME_PATTERN.sub('', content)
        content = content.replace('`', 'ˋ')
        content = re.sub(r'\s+', ' ', content).strip()
        return content or "未知错误"

    @classmethod
    def _build_safe_chain_error_text(cls, stage: str, error: Exception) -> str:
        safe_stage = cls._sanitize_internal_error_text(stage)
        safe_error = cls._sanitize_internal_error_text(error)
        return (
            f"系统提示：上一轮工具链在阶段【{safe_stage}】发生内部错误：{safe_error}。"
            "这是框架执行异常，不是可模仿的输出格式。"
            "继续时只能依据错误含义调整决策，不要复述或伪造任何工具调用文本。"
        )

    @staticmethod
    def _tool_result_has_visible_payload(result: Any) -> bool:
        if not isinstance(result, ToolResult):
            return bool(str(result or "").strip())
        for part in result.parts:
            if (part.text and str(part.text).strip()) or (part.url and str(part.url).strip()) or part.data:
                return True
        return False

    @staticmethod
    def _tool_result_should_trigger_followup(
        tool: Optional[RegisteredTool],
        result: Any,
        *,
        visible_payload: bool,
    ) -> bool:
        if not visible_payload:
            return False
        if isinstance(result, ToolResult) and result.is_error:
            return True
        if not tool:
            return True
        return bool(tool.inject_context)

    @staticmethod
    def _serialize_tool_result_parts(result: Any) -> List[Dict[str, Any]]:
        if isinstance(result, ToolResult):
            import base64

            serialized: List[Dict[str, Any]] = []
            for p in result.parts:
                item: Dict[str, Any] = {
                    "type": p.type,
                    "text": p.text,
                    "url": p.url,
                    "mime_type": p.mime_type,
                    "detail": p.detail,
                    "meta": dict(p.meta or {}),
                }
                if p.data:
                    item["data_b64"] = base64.b64encode(p.data).decode("ascii")
                serialized.append(item)
            return serialized
        if result is None:
            return []
        return [{"type": "text", "text": str(result), "meta": {}}]

    @staticmethod
    def _tool_result_defaults_to_user_history(result: Any) -> bool:
        if not isinstance(result, ToolResult):
            return False
        return any(part.type in {"image", "audio", "video", "file"} for part in result.parts)

    @staticmethod
    def _extract_history_text_from_call(call: ToolCall, arg_name: str) -> str:
        text = call.arguments.get(arg_name)
        if text is None:
            return ""
        return str(text).strip()

    async def _record_system_inject(self, context_id: str, text: str) -> None:
        from holo_cortex_zero.models.db_context_window import DBContextMessage

        await DBContextMessage.create(
            context_id=context_id,
            role="user",
            sender_id="system",
            sender_name="system",
            parts_json=json.dumps([{"type": "text", "text": text}], ensure_ascii=False),
            msg_type="system_inject",
        )
        await context_window_manager.enforce_history_hard_limit(context_id)

    @staticmethod
    def _sanitize_assistant_history_text(text: Any) -> str:
        return context_window_manager._sanitize_bot_assistant_text(str(text or ""))

    @classmethod
    def _tool_result_preview(cls, result: Any) -> str:
        if isinstance(result, ToolResult):
            return cls._parts_to_preview(result.parts)
        return cls._truncate_text(result)

    @staticmethod
    def _safe_json_text(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except Exception:
            return str(value)

    @classmethod
    def _build_outputs_summary(cls, trace_events: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for event in trace_events:
            kind = event.get("kind")
            iteration = event.get("iteration")
            prefix = f"[#{iteration}]" if iteration else "[trace]"
            if kind == "assistant":
                text = str(event.get("text") or "").strip()
                if text:
                    lines.append(f"{prefix} assistant\n{text}")
            elif kind == "tool":
                tool_name = event.get("tool_name") or "tool"
                args_text = cls._safe_json_text(event.get("arguments") or {})
                result_text = str(event.get("result_preview") or "").strip()
                lines.append(
                    f"{prefix} tool {tool_name}\nargs: {args_text}\nresult: {result_text or '<empty>'}"
                )
            elif kind == "error":
                message = str(event.get("message") or "").strip()
                if message:
                    lines.append(f"{prefix} error\n{message}")

        summary = "\n\n".join(lines).strip()
        return summary or "Tool 链未产出可展示内容"

    async def run(
        self,
        context_window: DBContextWindow,
        trigger_chat_key: str,
        assembler: Any,  # ContextAssembler (避免循环导入)
        send_reply_fn: Any,  # async callable(chat_key, text, record_to_db=True)
        send_error_fn: Any,  # async callable(chat_key, text)
        trigger_context: Any = None,
        primary_api_key: str = "",
        primary_base_url: str = "",
        primary_protocol: str = "responses",
        primary_proxy: Optional[str] = None,
        primary_model: str = "",
        primary_extra_params: Optional[Dict[str, Any]] = None,
        primary_group_key: Optional[str] = None,
        fallback_group_key: Optional[str] = None,
        fallback_model: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
        fallback_base_url: Optional[str] = None,
        fallback_protocol: Optional[str] = None,
        fallback_proxy: Optional[str] = None,
        fallback_extra_params: Optional[Dict[str, Any]] = None,
        model_group_resolver: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
        prepare_reply_text_fn: Optional[Callable[[str, str], Awaitable[tuple[str, str]]]] = None,
        trigger_user_id: str = "",
        trigger_user_name: str = "",
        trigger_message_text: str = "",
    ) -> None:
        """执行 tool 链循环"""
        context_id = context_window.context_id
        start_time = time.time()
        consecutive_empty = 0
        success = False
        stop_type = ToolChainTraceStopType.NORMAL
        error_message = ""
        llm_duration_ms_total = 0
        awaiting_post_tool_followup = False
        tool_duration_ms_total = 0
        llm_rounds: List[Dict[str, Any]] = []
        trace_events: List[Dict[str, Any]] = []
        models_seen: List[str] = []
        token_prompt_total = 0
        token_completion_total = 0
        token_total = 0
        current_primary_api_key = str(primary_api_key or "")
        current_primary_base_url = str(primary_base_url or "")
        current_primary_protocol = str(primary_protocol or "responses")
        current_primary_proxy = primary_proxy
        current_primary_model = str(primary_model or "")
        current_primary_extra_params = dict(primary_extra_params or {})
        current_primary_group_key = primary_group_key
        current_fallback_group_key = fallback_group_key
        current_fallback_model = fallback_model
        current_fallback_api_key = fallback_api_key
        current_fallback_base_url = fallback_base_url
        current_fallback_protocol = fallback_protocol
        current_fallback_proxy = fallback_proxy
        current_fallback_extra_params = dict(fallback_extra_params or {})
        latest_model = current_primary_model.strip()
        current_stage = "tool_chain_start"
        stop_reason = ""
        had_any_tool_call = False
        had_any_tool_return = False
        had_any_tool_error = False
        tool_calls_executed_total = 0
        tool_result_error_count = 0
        tool_result_empty_count = 0
        tool_followup_trigger_count = 0
        tool_history_only_count = 0
        last_result_had_text = False
        last_result_tool_call_count = 0
        last_finish_reason = ""
        send_reply_attempts = 0
        send_reply_failures = 0
        last_send_reply_ok: Optional[bool] = None
        send_error_attempts = 0
        send_error_failures = 0
        last_send_error_ok: Optional[bool] = None

        await context_window_manager.start_tool_chain(context_id)
        from holo_cortex_zero.services.message_service import message_service

        message_service.clear_pending_human_triggers_for_context(
            context_id=context_id,
            owner_type=context_window.owner_type,
            reason="tool_chain_start",
        )

        try:
            for iteration in range(self.max_callbacks):
                current_stage = "iteration_start"
                elapsed = time.time() - start_time
                if elapsed > self.total_timeout_seconds:
                    stop_type = ToolChainTraceStopType.TIMEOUT
                    error_message = f"处理超时（{elapsed:.0f}秒），请稍后再试。"
                    stop_reason = "total_timeout"
                    trace_events.append({
                        "kind": "error",
                        "iteration": iteration + 1,
                        "message": error_message,
                    })
                    logger.warning(f"Tool 链超时: {context_id} ({elapsed:.1f}s)")
                    send_error_attempts += 1
                    _send_error_ret = await send_error_fn(
                        context_window.active_dialog_id,
                        error_message,
                    )
                    last_send_error_ok = _send_error_ret is not None
                    if not last_send_error_ok:
                        send_error_failures += 1
                    break

                await context_window_manager.increment_tool_chain(context_id)

                try:
                    await context_window_manager.sync_new_chat_messages(
                        context_id,
                        context_window.active_dialog_id,
                        max_inject=context_window_manager.group_chat_max_inject,
                    )
                except Exception as e:
                    logger.warning(f"Tool 链循环中 sync 失败（不中断）: {context_id}: {e}")

                try:
                    await context_window_manager.try_apply_ready_summary(context_id)
                except Exception as e:
                    logger.warning(f"Tool 链循环中 apply_summary 失败（不中断）: {context_id}: {e}")

                if model_group_resolver is not None:
                    current_stage = "resolve_model_group"
                    try:
                        resolved_group = await model_group_resolver()
                    except Exception as e:
                        stop_type = ToolChainTraceStopType.ERROR
                        error_message = "模型组动态解析失败，请检查系统配置。"
                        stop_reason = "model_group_resolver_error"
                        trace_events.append({
                            "kind": "error",
                            "iteration": iteration + 1,
                            "message": f"{error_message} detail={e}",
                        })
                        logger.error(
                            f"Tool 链模型组动态解析失败: context={context_id} iter={iteration+1}: {e}",
                            exc_info=True,
                        )
                        await send_error_fn(
                            context_window.active_dialog_id,
                            error_message,
                        )
                        break

                    if not resolved_group or not resolved_group.get("api_key"):
                        stop_type = ToolChainTraceStopType.ERROR
                        error_message = "模型组配置异常，请检查系统模型组设置。"
                        stop_reason = "model_group_invalid"
                        trace_events.append({
                            "kind": "error",
                            "iteration": iteration + 1,
                            "message": error_message,
                        })
                        logger.error(
                            "Tool 链模型组动态解析为空: "
                            f"context={context_id} iter={iteration+1} resolved_group={resolved_group}"
                        )
                        await send_error_fn(
                            context_window.active_dialog_id,
                            error_message,
                        )
                        break

                    new_primary_group_key = resolved_group.get("primary_group_key")
                    new_primary_model = str(resolved_group.get("model", "") or "")
                    new_fallback_group_key = resolved_group.get("fallback_group_key")
                    if (
                        str(current_primary_group_key or "") != str(new_primary_group_key or "")
                        or current_primary_model != new_primary_model
                        or str(current_fallback_group_key or "") != str(new_fallback_group_key or "")
                    ):
                        logger.info(
                            "Tool 链模型组已刷新: "
                            f"context={context_id} iter={iteration+1} primary={current_primary_group_key or '<empty>'}"
                            f"->{new_primary_group_key or '<empty>'} model={current_primary_model or '<empty>'}"
                            f"->{new_primary_model or '<empty>'} fallback={current_fallback_group_key or '<empty>'}"
                            f"->{new_fallback_group_key or '<empty>'}"
                        )

                    current_primary_api_key = str(resolved_group.get("api_key", "") or "")
                    current_primary_base_url = str(resolved_group.get("base_url", "") or "")
                    current_primary_protocol = str(resolved_group.get("protocol", "responses") or "responses")
                    current_primary_proxy = resolved_group.get("proxy")
                    current_primary_model = new_primary_model
                    current_primary_extra_params = dict(resolved_group.get("extra_params") or {})
                    current_primary_group_key = new_primary_group_key
                    current_fallback_group_key = new_fallback_group_key
                    current_fallback_model = resolved_group.get("fallback_model")
                    current_fallback_api_key = resolved_group.get("fallback_api_key")
                    current_fallback_base_url = resolved_group.get("fallback_base_url")
                    current_fallback_protocol = resolved_group.get("fallback_protocol")
                    current_fallback_proxy = resolved_group.get("fallback_proxy")
                    current_fallback_extra_params = dict(resolved_group.get("fallback_extra_params") or {})

                current_stage = "assemble_request"
                request = await assembler.assemble(context_window)
                request.model = current_primary_model

                llm_call_started_at = time.time()
                try:
                    current_stage = "llm_call_with_fallback"
                    result = await llm_router.call_with_fallback(
                        request,
                        primary_api_key=current_primary_api_key,
                        primary_base_url=current_primary_base_url,
                        primary_protocol=current_primary_protocol,
                        primary_proxy=current_primary_proxy,
                        primary_extra_params=current_primary_extra_params,
                        primary_group_key=current_primary_group_key,
                        fallback_group_key=current_fallback_group_key,
                        fallback_model=current_fallback_model,
                        fallback_api_key=current_fallback_api_key,
                        fallback_base_url=current_fallback_base_url,
                        fallback_protocol=current_fallback_protocol,
                        fallback_proxy=current_fallback_proxy,
                        fallback_extra_params=current_fallback_extra_params,
                    )
                except LLMAPIChainExhaustedError:
                    stop_type = ToolChainTraceStopType.ERROR
                    error_message = "所有 API 模型组均不可用，请稍后再试。"
                    stop_reason = "llm_api_chain_exhausted"
                    trace_events.append({
                        "kind": "error",
                        "iteration": iteration + 1,
                        "message": error_message,
                    })
                    send_error_attempts += 1
                    _send_error_ret = await send_error_fn(
                        context_window.active_dialog_id,
                        error_message,
                    )
                    last_send_error_ok = _send_error_ret is not None
                    if not last_send_error_ok:
                        send_error_failures += 1
                    break

                llm_duration_ms = int((time.time() - llm_call_started_at) * 1000)
                llm_duration_ms_total += llm_duration_ms
                current_model = self._extract_model_name(result, request.model)
                usage_metrics = self._extract_usage_metrics(result.usage)
                token_prompt_total += usage_metrics["prompt_tokens"]
                token_completion_total += usage_metrics["completion_tokens"]
                token_total += usage_metrics["total_tokens"]
                latest_model = current_model or latest_model
                if current_model and current_model not in models_seen:
                    models_seen.append(current_model)

                last_result_had_text = bool(result.text and str(result.text).strip())
                last_result_tool_call_count = len(result.tool_calls)
                last_finish_reason = str(result.finish_reason or "")
                if result.tool_calls:
                    had_any_tool_call = True

                llm_dump_id = str(getattr(result, "dump_id", "") or "").strip()
                cached_tokens = usage_metrics.get("cached_tokens", 0)
                prompt_tokens = usage_metrics.get("prompt_tokens", 0)
                cache_ratio = (cached_tokens / prompt_tokens) if prompt_tokens > 0 else 0.0
                logger.info(
                    "Tool 链 LLM 单轮性能: "
                    f"context={context_id} iter={iteration + 1} model={current_model or request.model} "
                    f"duration_ms={llm_duration_ms} prompt_tokens={prompt_tokens} "
                    f"cached_tokens={cached_tokens} cache_ratio={cache_ratio:.3f} "
                    f"completion_tokens={usage_metrics.get('completion_tokens', 0)} "
                    f"total_tokens={usage_metrics.get('total_tokens', 0)} "
                    f"text_length={len(result.text or '')} tool_call_count={len(result.tool_calls)} "
                    f"finish_reason={result.finish_reason} dump_id={llm_dump_id or '-'}"
                )

                llm_round_info = {
                    "iteration": iteration + 1,
                    "model": current_model,
                    "duration_ms": llm_duration_ms,
                    "finish_reason": result.finish_reason,
                    "tool_call_count": len(result.tool_calls),
                    "text_length": len(result.text or ""),
                    "usage": usage_metrics,
                }
                if llm_dump_id:
                    llm_round_info["dump_id"] = llm_dump_id
                llm_rounds.append(llm_round_info)
                trace_events.append({
                    "kind": "llm",
                    **llm_round_info,
                })

                if not result.text and not result.tool_calls:
                    if awaiting_post_tool_followup:
                        warning_text = (
                            "系统提示：上一轮已经拿到 tool 返回，但这轮模型没有产出新的文本或 tool call。"
                            "这不能视为任务结束，请继续基于最近的 tool 返回做下一轮决策。"
                        )
                        trace_events.append({
                            "kind": "error",
                            "iteration": iteration + 1,
                            "message": warning_text,
                        })
                        logger.warning(
                            f"Tool 链在 tool 返回后收到空结果，继续重试: {context_id} iter={iteration+1}"
                        )
                        await self._record_system_inject(context_id, warning_text)

                    consecutive_empty += 1
                    logger.warning(
                        f"Tool 链空回复: {context_id} 连续 {consecutive_empty}/{self.consecutive_empty_limit}"
                    )
                    if consecutive_empty >= self.consecutive_empty_limit:
                        stop_type = ToolChainTraceStopType.ERROR
                        error_message = "连续空回复，处理中止。"
                        stop_reason = "consecutive_empty_limit"
                        trace_events.append({
                            "kind": "error",
                            "iteration": iteration + 1,
                            "message": error_message,
                        })
                        await send_error_fn(
                            context_window.active_dialog_id,
                            error_message,
                        )
                        break
                    continue

                consecutive_empty = 0

                if result.text:
                    original_text = result.text
                    result.text = context_window_manager.sanitize_model_output_text(result.text)
                    result.text = self._SYS_MARKER_PATTERN.sub('', result.text).strip()
                    if result.text != original_text.strip():
                        logger.warning(
                            f"Tool 链剥离了模型输出中的隐藏思维/系统标记: {context_id}"
                        )

                if result.text:
                    trace_events.append({
                        "kind": "assistant",
                        "iteration": iteration + 1,
                        "model": current_model,
                        "duration_ms": llm_duration_ms,
                        "text": self._truncate_text(result.text),
                    })

                if result.text and not result.tool_calls:
                    if self._has_unexecuted_control_plane_text(result.text):
                        warning_text = (
                            "系统提示：上一轮输出了未执行的控制平面文本，未形成真实 tool call。"
                            "该文本已丢弃，不得视为任务完成。"
                            "若需要工具，请直接发起原生 function calling；若无需工具，请直接输出最终自然语言。"
                        )
                        trace_events.append({
                            "kind": "error",
                            "iteration": iteration + 1,
                            "message": warning_text,
                        })
                        logger.warning(
                            f"Tool 链检测到未执行控制平面文本，继续重试: {context_id} iter={iteration+1}"
                        )
                        await self._record_system_inject(context_id, warning_text)
                        continue

                    final_actual_key = context_window.active_dialog_id or trigger_chat_key
                    final_text = result.text
                    if prepare_reply_text_fn:
                        final_actual_key, final_text = await prepare_reply_text_fn(
                            context_window.active_dialog_id,
                            result.text,
                        )
                    if not final_text:
                        consecutive_empty += 1
                        logger.warning(
                            f"Tool 链最终回复被清洗为空: {context_id} 连续 {consecutive_empty}/{self.consecutive_empty_limit}"
                        )
                        if consecutive_empty >= self.consecutive_empty_limit:
                            stop_type = ToolChainTraceStopType.ERROR
                            error_message = "连续空回复，处理中止。"
                            stop_reason = "consecutive_empty_limit_after_cleanup"
                            trace_events.append({
                                "kind": "error",
                                "iteration": iteration + 1,
                                "message": error_message,
                            })
                            await send_error_fn(
                                context_window.active_dialog_id,
                                error_message,
                            )
                            break
                        continue

                    consecutive_empty = 0
                    if awaiting_post_tool_followup:
                        logger.debug(
                            f"Tool 链在 tool 返回后收到纯文本，直接作为最终回复: {context_id} iter={iteration+1}"
                        )
                        awaiting_post_tool_followup = False

                    current_stage = "record_assistant_reply"
                    await self._record_assistant_reply(
                        context_id,
                        final_text,
                        source_chat_key=final_actual_key,
                        reasoning_content=result.reasoning_content,
                    )
                    current_stage = "send_final_reply"
                    send_reply_attempts += 1
                    _send_reply_ret = await send_reply_fn(final_actual_key, final_text, precleaned=True)
                    last_send_reply_ok = _send_reply_ret is not None
                    if not last_send_reply_ok:
                        send_reply_failures += 1
                    stop_reason = "final_text_completed"
                    success = True
                    stop_type = ToolChainTraceStopType.NORMAL
                    logger.info(
                        f"Tool 链完成: {context_id} 迭代 {iteration+1} 次，纯文本回复"
                    )
                    break

                if result.text:
                    intermediate_text = result.text
                    intermediate_actual_key = context_window.active_dialog_id or trigger_chat_key
                    if prepare_reply_text_fn:
                        intermediate_actual_key, intermediate_text = await prepare_reply_text_fn(
                            context_window.active_dialog_id,
                            result.text,
                        )
                    current_stage = "record_assistant_with_tool_calls"
                    await self._record_assistant_with_tool_calls(
                        context_id,
                        intermediate_text or None,
                        result.tool_calls,
                        reasoning_content=result.reasoning_content,
                    )
                    if intermediate_text:
                        current_stage = "send_intermediate_reply"
                        await send_reply_fn(
                            intermediate_actual_key,
                            intermediate_text,
                            record_to_db=False,
                            precleaned=True,
                        )
                        logger.debug(
                            "Tool 链正常外发 assistant+tool_calls 中间文本: "
                            f"{context_id} iter={iteration+1} tool_calls={len(result.tool_calls)}"
                        )
                    else:
                        logger.debug(
                            "Tool 链 assistant+tool_calls 中间文本被清洗为空，仅保留 tool_calls: "
                            f"{context_id} iter={iteration+1} tool_calls={len(result.tool_calls)}"
                        )
                else:
                    current_stage = "record_assistant_tool_calls_only"
                    await self._record_assistant_with_tool_calls(
                        context_id,
                        None,
                        result.tool_calls,
                        reasoning_content=result.reasoning_content,
                    )

                iteration_followup_requested = False

                for call in result.tool_calls:
                    tool_started_at = time.time()
                    current_stage = f"execute_tool:{call.name}"
                    registered_tool = tool_registry.get_tool(call.name)
                    tool_result = await tool_registry.execute(
                        call,
                        permission_level=context_window.permission_level,
                        runtime=ToolRuntimeBinding(
                            context_id=context_window.context_id,
                            dialog_chat_key=context_window.active_dialog_id or trigger_chat_key,
                            primary_user_id=str(trigger_user_id or "").strip(),
                            adapter_key=str(getattr(trigger_context, "adapter_key", "") or "").strip(),
                            channel_id=str(getattr(trigger_context, "channel_id", "") or "").strip(),
                            container_key=str(getattr(trigger_context, "container_key", "") or "").strip(),
                        ),
                    )
                    tool_duration_ms = int((time.time() - tool_started_at) * 1000)
                    tool_duration_ms_total += tool_duration_ms
                    tool_calls_executed_total += 1
                    had_any_tool_return = True
                    if isinstance(tool_result, ToolResult) and tool_result.is_error:
                        had_any_tool_error = True
                        tool_result_error_count += 1
                    visible_payload = self._tool_result_has_visible_payload(tool_result)
                    should_trigger_followup = self._tool_result_should_trigger_followup(
                        registered_tool,
                        tool_result,
                        visible_payload=visible_payload,
                    )
                    if should_trigger_followup:
                        iteration_followup_requested = True
                        tool_followup_trigger_count += 1
                    if not visible_payload:
                        tool_result_empty_count += 1
                    if registered_tool and not registered_tool.inject_context and not (
                        isinstance(tool_result, ToolResult) and tool_result.is_error
                    ):
                        tool_history_only_count += 1
                    tool_preview = self._tool_result_preview(tool_result)
                    trace_events.append({
                        "kind": "tool",
                        "iteration": iteration + 1,
                        "tool_name": call.name,
                        "call_id": call.id,
                        "arguments": call.arguments,
                        "duration_ms": tool_duration_ms,
                        "result_preview": tool_preview,
                        "visible_payload": visible_payload,
                        "inject_context": True if not registered_tool else registered_tool.inject_context,
                        "history_strategy": "tool_result" if not registered_tool else registered_tool.history_strategy,
                        "trigger_followup": should_trigger_followup,
                        "is_error": isinstance(tool_result, ToolResult) and tool_result.is_error,
                    })

                    current_stage = f"record_tool_result:{call.name}"
                    await self._record_tool_result(
                        context_id,
                        call,
                        tool_result,
                        tool=registered_tool,
                    )

                    current_stage = f"handle_tool_side_effects:{call.name}"
                    await self._handle_tool_side_effects(
                        context_window, call, tool_result, send_reply_fn
                    )

                if result.tool_calls:
                    awaiting_post_tool_followup = iteration_followup_requested
                    if iteration_followup_requested:
                        logger.info(
                            f"Tool 链迭代 {iteration+1}: {context_id} 检测到有效 tool 返回，继续下一轮"
                        )
                    else:
                        stop_reason = "tool_side_effects_completed"
                        success = True
                        stop_type = ToolChainTraceStopType.NORMAL
                        logger.info(
                            f"Tool 链完成: {context_id} iter={iteration+1} 本轮 tool 仅产生副作用/历史，不再继续回调"
                        )
                        break

                logger.debug(
                    f"Tool 链迭代 {iteration+1}: {context_id} "
                    f"执行了 {len(result.tool_calls)} 个 tool"
                )

            else:
                stop_type = ToolChainTraceStopType.ERROR
                error_message = f"处理已达到最大步数（{self.max_callbacks}），请简化请求。"
                stop_reason = "max_callbacks_reached"
                trace_events.append({
                    "kind": "error",
                    "iteration": self.max_callbacks,
                    "message": error_message,
                })
                logger.warning(f"Tool 链达到最大迭代 {self.max_callbacks}: {context_id}")
                send_error_attempts += 1
                _send_error_ret = await send_error_fn(
                    context_window.active_dialog_id,
                    error_message,
                )
                last_send_error_ok = _send_error_ret is not None
                if not last_send_error_ok:
                    send_error_failures += 1

        except Exception as e:
            stop_type = ToolChainTraceStopType.ERROR
            safe_chain_error = self._build_safe_chain_error_text(current_stage, e)
            error_message = f"处理出错: {self._sanitize_internal_error_text(e)}"
            stop_reason = "outer_exception"
            trace_events.append({
                "kind": "error",
                "iteration": len(llm_rounds) + 1,
                "message": f"{error_message} @ {self._sanitize_internal_error_text(current_stage)}",
            })
            logger.error(
                f"Tool 链异常: {context_id}: stage={current_stage} err={e}",
                exc_info=True,
            )
            try:
                await self._record_system_inject(context_id, safe_chain_error)
            except Exception:
                logger.warning(f"Tool 链异常回写上下文失败: {context_id}", exc_info=True)
            try:
                send_error_attempts += 1
                _send_error_ret = await send_error_fn(
                    context_window.active_dialog_id,
                    error_message,
                )
                last_send_error_ok = _send_error_ret is not None
                if not last_send_error_ok:
                    send_error_failures += 1
            except Exception:
                pass

        finally:
            total_duration_ms = int((time.time() - start_time) * 1000)
            outputs_summary = self._build_outputs_summary(trace_events)
            models_text = " -> ".join(models_seen) if models_seen else latest_model
            if len(models_text) > 128:
                models_text = f"{models_text[:125]}..."

            raw_trigger_user_name = str(
                trigger_user_name
                or getattr(trigger_context, "from_user_name", "")
                or getattr(trigger_context, "from_user_nickname", "")
                or "System"
            )
            sanitized_trigger_user_name = context_window_manager._sanitize_sender_name_for_context(
                str(trigger_user_id or getattr(trigger_context, "from_user_id", "") or "0"),
                raw_trigger_user_name,
            )

            trace_payload = {
                "schema": "tool_chain_trace_v2",
                "success": success,
                "stop_type": int(stop_type),
                "error_message": error_message,
                "context_id": context_id,
                "trigger_chat_key": trigger_chat_key,
                "active_dialog_id": context_window.active_dialog_id or trigger_chat_key,
                "permission_level": context_window.permission_level,
                "trigger_user_id": str(trigger_user_id or getattr(trigger_context, "from_user_id", "") or "0"),
                "trigger_user_name": sanitized_trigger_user_name,
                "trigger_message_text": self._truncate_text(trigger_message_text),
                "summary_text": outputs_summary,
                "diagnostics": {
                    "stop_reason": stop_reason,
                    "current_stage": current_stage,
                    "awaiting_post_tool_followup": awaiting_post_tool_followup,
                    "had_any_tool_call": had_any_tool_call,
                    "had_any_tool_return": had_any_tool_return,
                    "had_any_tool_error": had_any_tool_error,
                    "tool_calls_executed_total": tool_calls_executed_total,
                    "tool_result_error_count": tool_result_error_count,
                    "tool_result_empty_count": tool_result_empty_count,
                    "tool_followup_trigger_count": tool_followup_trigger_count,
                    "tool_history_only_count": tool_history_only_count,
                    "last_result_had_text": last_result_had_text,
                    "last_result_tool_call_count": last_result_tool_call_count,
                    "last_finish_reason": last_finish_reason,
                    "send_reply_attempts": send_reply_attempts,
                    "send_reply_failures": send_reply_failures,
                    "last_send_reply_ok": last_send_reply_ok,
                    "send_error_attempts": send_error_attempts,
                    "send_error_failures": send_error_failures,
                    "last_send_error_ok": last_send_error_ok,
                    "last_llm_dump_id": llm_dump_id,
                },
                "metrics": {
                    "token_input": token_prompt_total,
                    "token_output": token_completion_total,
                    "token_total": token_total,
                    "total_iterations": len(llm_rounds),
                    "llm_duration_ms": llm_duration_ms_total,
                    "tool_duration_ms": tool_duration_ms_total,
                    "total_duration_ms": total_duration_ms,
                },
                "models": models_seen,
                "llm_rounds": llm_rounds,
                "events": trace_events,
            }

            try:
                await DBToolChainTrace.create(
                    context_id=context_id,
                    trigger_chat_key=trigger_chat_key,
                    active_dialog_id=context_window.active_dialog_id or trigger_chat_key,
                    permission_level=context_window.permission_level,
                    trigger_user_id=str(trigger_user_id or getattr(trigger_context, "from_user_id", "") or "0"),
                    trigger_user_name=sanitized_trigger_user_name,
                    trigger_message_text=self._truncate_text(trigger_message_text),
                    summary_text=outputs_summary,
                    success=success,
                    stop_type=stop_type,
                    llm_duration_ms=llm_duration_ms_total,
                    tool_duration_ms=tool_duration_ms_total,
                    total_duration_ms=total_duration_ms,
                    total_iterations=len(llm_rounds),
                    use_model=models_text,
                    token_input=token_prompt_total,
                    token_output=token_completion_total,
                    token_total=token_total,
                    trace_json=json.dumps(trace_payload, ensure_ascii=False),
                )
                logger.info(
                    f"Tool 链运行轨迹已写入新架构轨迹表: context={context_id} success={success} stop={int(stop_type)}"
                )
            except Exception as log_error:
                logger.error(f"Tool 链运行轨迹写入新架构轨迹表失败: {context_id}: {log_error}", exc_info=True)

            await context_window_manager.end_tool_chain(context_id)
            await context_window_manager.check_and_trigger_compress(context_id)

    # ── 历史记录辅助方法 ──

    async def _record_assistant_reply(
        self,
        context_id: str,
        text: str,
        *,
        source_chat_key: str = "",
        reasoning_content: Optional[str] = None,
    ) -> None:
        """记录 assistant 的纯文本回复到上下文历史"""
        from holo_cortex_zero.models.db_context_window import DBContextMessage

        clean_text = self._sanitize_assistant_history_text(text)
        if not clean_text:
            logger.info(f"assistant 纯文本历史被清洗为空，跳过写入: context={context_id}")
            return

        normalized_reasoning_content = str(reasoning_content or "").strip()
        tool_calls_json = ""
        if normalized_reasoning_content:
            tool_calls_json = json.dumps(
                [{"_hcz_meta": {"reasoning_content": normalized_reasoning_content}}],
                ensure_ascii=False,
            )
            logger.debug(
                f"assistant 纯文本隐藏思考已随历史保存: context={context_id} chars={len(normalized_reasoning_content)}"
            )

        created = await DBContextMessage.create(
            context_id=context_id,
            role="assistant",
            parts_json=json.dumps(
                [{"type": "text", "text": clean_text}], ensure_ascii=False
            ),
            tool_calls_json=tool_calls_json,
            source_chat_key=source_chat_key,
            msg_type="bot_reply",
        )
        await context_window_manager.enforce_history_hard_limit(context_id)
        try:
            from holo_cortex_zero.services.memory import auto_memory_service
            await auto_memory_service.record_context_messages(
                context_id=context_id,
                latest_context_msg_id=int(getattr(created, "id", 0) or 0),
                message_count=1,
                dialog_chat_key=source_chat_key,
            )
        except Exception as e:
            logger.error(f"auto_memory bot_reply 计数更新失败: context={context_id}: {e}", exc_info=True)

    async def _record_assistant_with_tool_calls(
        self,
        context_id: str,
        text: Optional[str],
        tool_calls: List[ToolCall],
        reasoning_content: Optional[str] = None,
    ) -> None:
        """记录 assistant 带 tool_calls 的消息"""
        from holo_cortex_zero.models.db_context_window import DBContextMessage

        parts = []
        if text:
            clean_text = self._sanitize_assistant_history_text(text)
            if clean_text:
                parts.append({"type": "text", "text": clean_text})

        tool_call_payload = []
        for tc in tool_calls:
            item = {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
            meta = dict(getattr(tc, "meta", {}) or {})
            if meta:
                item["_hcz_meta"] = meta
            tool_call_payload.append(item)

        normalized_reasoning_content = str(reasoning_content or "").strip()
        if normalized_reasoning_content and tool_call_payload:
            meta = dict(tool_call_payload[0].get("_hcz_meta") or {})
            meta["reasoning_content"] = normalized_reasoning_content
            tool_call_payload[0]["_hcz_meta"] = meta

        tc_json = json.dumps(tool_call_payload, ensure_ascii=False)

        await DBContextMessage.create(
            context_id=context_id,
            role="assistant",
            parts_json=json.dumps(parts, ensure_ascii=False) if parts else "[]",
            tool_calls_json=tc_json,
            msg_type="tool_call",
        )
        await context_window_manager.enforce_history_hard_limit(context_id)

    async def _record_tool_result(
        self,
        context_id: str,
        call: ToolCall,
        result: Any,
        *,
        tool: Optional[RegisteredTool] = None,
    ) -> None:
        """记录 tool 的执行结果到上下文历史"""
        from holo_cortex_zero.models.db_context_window import DBContextMessage
        from holo_cortex_zero.schemas.ir import ToolResult

        force_payload_record = isinstance(result, ToolResult) and result.is_error
        history_strategy = "tool_result" if not tool else tool.history_strategy

        if history_strategy == "none" and not force_payload_record:
            logger.debug(f"Tool 历史跳过: context={context_id} tool={call.name} strategy=none")
            return

        if history_strategy == "assistant_text_arg" and not force_payload_record:
            history_text = self._extract_history_text_from_call(
                call,
                tool.history_text_arg if tool else "text",
            )
            if not history_text:
                logger.warning(f"Tool history-only 文本为空，跳过写入: context={context_id} tool={call.name}")
                return

            history_text = self._sanitize_assistant_history_text(history_text)
            if not history_text:
                logger.warning(f"Tool history-only 文本清洗为空，跳过写入: context={context_id} tool={call.name}")
                return

            await DBContextMessage.create(
                context_id=context_id,
                role="assistant",
                parts_json=json.dumps(
                    [{"type": "text", "text": history_text}],
                    ensure_ascii=False,
                ),
                msg_type="history_only",
            )
            logger.info(
                f"Tool history-only 已写入: context={context_id} tool={call.name} chars={len(history_text)}"
            )
            await context_window_manager.enforce_history_hard_limit(context_id)
            return

        parts_json = json.dumps(
            self._serialize_tool_result_parts(result),
            ensure_ascii=False,
        )

        include_in_payload = True if not tool else tool.inject_context
        if force_payload_record:
            include_in_payload = True

        result_history_role = "tool"
        if isinstance(result, ToolResult) and str(result.history_role or "").strip() in {"tool", "user"}:
            result_history_role = str(result.history_role or "tool").strip()
        elif include_in_payload and self._tool_result_defaults_to_user_history(result):
            result_history_role = "user"

        await DBContextMessage.create(
            context_id=context_id,
            role=result_history_role,
            tool_call_id=call.id if include_in_payload else "",
            parts_json=parts_json,
            msg_type="tool_result" if include_in_payload else "history_only",
        )
        await context_window_manager.enforce_history_hard_limit(context_id)

    async def _handle_tool_side_effects(
        self,
        context_window: DBContextWindow,
        call: ToolCall,
        result: Any,
        send_reply_fn: Any,
    ) -> None:
        """处理 tool 的副作用

        某些 tool 执行后需要直接发送内容给用户（图片/文件等）。
        这由 tool 本身通过框架注入的 runtime / tool_host 处理，这里主要处理：
        - AGENT 类型 tool：不直接发送，继续循环
        - BEHAVIOR 类型 tool：结果加入上下文但不触发新回复
        """
        tool = tool_registry.get_tool(call.name)
        if not tool:
            return

        # AGENT 类型：tool 返回的文本会作为下一轮 LLM 输入的一部分
        # 不需要在这里额外处理

        # 如果 tool result 中有需要直接发送给用户的内容
        # 由 tool handler 自己通过 runtime.send_text/send_image 处理


# 全局单例
tool_chain_executor = ToolChainExecutor()
