"""/responses 协议发射器

主干说明：
- 默认优先走通用兼容格式，只在已确认的本地 vLLM 场景启用最小兼容补丁。
- 通用缓存优化保留在主链：基于 `context_id` 的轻量前缀快照 + LCP（最长公共前缀）选锚点。
- 这套主链缓存优化服务所有普通 `/responses` 目标，不依赖旧的 system 文本规则。

分支说明：
- 个别供应商可能有独立的协议兼容问题，此时允许在主链之上叠加“分支兼容”。
- 这类分支只负责请求 / 返回兼容，不再承诺供应商缓存语义。
- 后续扩展时必须保持这种关系：主链负责通用请求形状与通用缓存优化，分支只补该供应商独有的协议兼容语义。

遵循 docs/guides/local-vllm-responses.md 中的推荐格式：
- 统一使用结构化 input 数组
- input_image 必须带 detail: "auto"
- 默认只取 message -> content -> output_text
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.uniapi_hosts import UNIAPI_HOSTS
from holo_cortex_zero.schemas.ir import (
    GenerationRequest,
    GenerationResult,
    MessagePart,
    MessageTurn,
    ToolCall,
    ToolSpec,
)

from .base import BaseEmitter, EmitterMediaCapabilities
from .model_group_params import MODEL_GROUP_CACHE_TRANSPORT_PROFILE_EXTRA_KEY
from .prompt_logging import dump_prompt_request, dump_prompt_response
from .qwen_compat import merge_tool_calls, parse_qwen_tool_calls
from .reasoning_text import (
    build_reasoning_content,
    extract_text_reasoning_content,
    format_text_reasoning_for_history,
    get_responses_reasoning_items,
    get_text_reasoning_content,
)


VLLM_MAX_IMAGE_LONG_EDGE = 2048
LOCAL_VLLM_FIXED_IMAGE_MAX_LONG_EDGE = 640
LOCAL_OPENAI_COMPAT_HOSTS = {
    "127.0.0.1",
    "::1",
    "localhost",
    "host.docker.internal",
    "172.19.0.1",
}
RESPONSES_TOOL_RESULT_MODE_NATIVE = "native"
RESPONSES_MESSAGE_ROLES = {"system", "user", "assistant"}
RESPONSES_GENERIC_CACHE_CONTROL = {"type": "ephemeral"}
RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS = 50.0
RESPONSES_TOTAL_TIMEOUT_SECONDS = 800.0
LOCAL_VLLM_RESPONSES_TIMEOUT_SECONDS = 300.0
RESPONSES_CONNECT_TIMEOUT_SECONDS = 10.0
RESPONSES_WRITE_TIMEOUT_SECONDS = 30.0
RESPONSES_POOL_TIMEOUT_SECONDS = 30.0
UNI_QWEN_NON_STREAM_HOSTS = set(UNIAPI_HOSTS)
UNI_QWEN_NON_STREAM_MODELS = {"qwen3.5-plus"}
UNI_QWEN_NON_STREAM_TIMEOUT_SECONDS = 50.0
UNI_GROK_RESPONSES_HOSTS = set(UNIAPI_HOSTS)
GPT_RESPONSES_RELAY_HOSTS = {"api2.penguinsaichat.dpdns.org"}
RESPONSES_TRANSPORT_CONTROL_KEYS = {
    "__transport",
    "_transport",
    "transport",
    "api_mode",
    "wire_api",
    "force_stream",
    "force_stream_mode",
    "responses_legacy_role_rewrite",
    "replay_reasoning_content",
    MODEL_GROUP_CACHE_TRANSPORT_PROFILE_EXTRA_KEY,
}
RESPONSES_DEVELOPER_INSTRUCTION_KEYS = (
    "developer_instruction",
    "developer_message",
    "deep_developer_instruction",
)


def _get_responses_stream_idle_timeout_seconds() -> float:
    raw_value = getattr(config, "LLM_RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS", RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS)
    try:
        return max(float(raw_value or RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS), 1.0)
    except (TypeError, ValueError):
        logger.warning(
            "[responses][timeout] invalid LLM_RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS, fallback to default: "
            f"value={raw_value!r} default={RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS}"
        )
        return RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS


class ResponsesEmitter(BaseEmitter):
    """/responses 协议发射器"""

    @staticmethod
    def _merge_leading_system_turns(messages: List[MessageTurn]) -> List[MessageTurn]:
        """Fold consecutive leading system turns into one mainline `/responses` message.

        Mainline:
            Keep the shared IR unchanged for upper layers, but normalize the emitted
            `/responses` payload so the opening system block is always a single
            leading message.

        Why here:
            Some OpenAI-compatible `/responses` targets reject payloads with more
            than one consecutive leading `role=system` message, even when every
            system turn is already at the beginning. Folding them in the emitter
            keeps the fix generic and avoids per-caller protocol branches.
        """
        if len(messages) < 2:
            return messages

        leading_system_count = 0
        merged_parts: List[MessagePart] = []
        for turn in messages:
            if turn.role != "system":
                break
            leading_system_count += 1
            merged_parts.extend(turn.parts)

        if leading_system_count <= 1:
            return messages

        logger.info(
            "[responses][compat] merged leading system turns for /responses payload: "
            f"count={leading_system_count}"
        )
        return [MessageTurn(role="system", parts=merged_parts)] + messages[leading_system_count:]

    def get_media_capabilities(self) -> EmitterMediaCapabilities:
        return EmitterMediaCapabilities(
            name="responses",
            accepts_image_parts=True,
            accepts_audio_parts=False,
            accepts_video_parts=False,
            native_tool_calling=True,
            notes="responses 当前主链原生发送图片；音频/视频/文件在发射器内统一降级为文本。",
        )

    @staticmethod
    def _parse_base_url(base_url: str) -> tuple[str, str]:
        raw = str(base_url or "").strip()
        if not raw:
            return "", ""
        try:
            parsed = urlparse(raw)
        except ValueError:
            return "", ""
        return str(parsed.hostname or "").strip().lower(), str(parsed.path or "").strip().lower()

    @staticmethod
    def _model_looks_like_gpt(model: str) -> bool:
        return str(model or "").strip().lower().startswith("gpt-")

    @staticmethod
    def _is_gpt_responses_relay_target(*, base_url: str, model: str) -> bool:
        host, _ = ResponsesEmitter._parse_base_url(base_url)
        return host in GPT_RESPONSES_RELAY_HOSTS and ResponsesEmitter._model_looks_like_gpt(model)

    @staticmethod
    def _is_any_gpt_responses_target(*, base_url: str, model: str) -> bool:
        return ResponsesEmitter._is_gpt_responses_relay_target(base_url=base_url, model=model)

    @staticmethod
    def _is_uni_grok_responses_target(*, base_url: str, model: str) -> bool:
        host, _ = ResponsesEmitter._parse_base_url(base_url)
        normalized_model = str(model or "").strip().lower()
        return host in UNI_GROK_RESPONSES_HOSTS and normalized_model.startswith("grok-")

    @staticmethod
    def _responses_compat_reason(*, base_url: str, model: str) -> str:
        """Return the compatibility branch reason for `/responses` route shaping.

        Mainline:
            `/responses` keeps one generic payload + cache mainline.

        Branch compatibility:
            Some upstream relays expose a `/responses`-shaped endpoint but reject
            selected OpenAI-compatible request fields. These branches only prune the
            incompatible fields; they do not fork a separate request builder or
            parallel mainline.
        """
        if ResponsesEmitter._is_uni_qwen_non_stream_target(base_url=base_url, model=model):
            return "uni_qwen"

        host, path = ResponsesEmitter._parse_base_url(base_url)
        normalized_path = path.rstrip("/")
        if host.endswith("volces.com") and normalized_path.endswith("/api/v3"):
            return "ark_api_v3"

        return ""

    @staticmethod
    def _strip_content_cache_control_in_place(payload: Dict[str, Any]) -> bool:
        stripped = False
        for item in payload.get("input", []) or []:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for seg in content:
                if isinstance(seg, dict) and "cache_control" in seg:
                    seg.pop("cache_control", None)
                    stripped = True
        return stripped

    @staticmethod
    def _strip_top_level_cache_control_in_place(payload: Dict[str, Any]) -> bool:
        if "cache_control" not in payload:
            return False
        payload.pop("cache_control", None)
        return True

    @staticmethod
    def _rewrite_gpt_relay_assistant_input_text_in_place(payload: Dict[str, Any]) -> int:
        rewritten = 0
        for item in payload.get("input", []) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() != "message":
                continue
            if str(item.get("role") or "").strip().lower() != "assistant":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for seg in content:
                if not isinstance(seg, dict):
                    continue
                if str(seg.get("type") or "").strip().lower() != "input_text":
                    continue
                seg["type"] = "output_text"
                rewritten += 1
        return rewritten

    def _apply_gpt_route_payload_compat(
        self,
        payload: Dict[str, Any],
        *,
        base_url: str,
        model: str,
    ) -> None:
        """Apply GPT-route-only payload shaping.

        Mainline `/responses` behavior stays generic; only GPT relay routes
        receive one compatibility adjustment: remove content-block cache_control.
        """
        if self._is_gpt_responses_relay_target(base_url=base_url, model=model):
            if self._strip_content_cache_control_in_place(payload):
                logger.info(
                    "[responses][gpt] relay payload adjusted: drop content cache_control "
                    f"base_url={base_url} model={model}"
                )

    def _parse_sse_text_response(self, raw_text: str, *, log_dir: str, ts: str) -> GenerationResult:
        """Parse a text/plain SSE body returned from a non-standard upstream."""
        accumulated_text = ""
        final_result: Optional[GenerationResult] = None
        last_event_type = ""

        for raw_line in str(raw_text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("event: "):
                last_event_type = line[7:].strip()
                continue
            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                event_data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = str(event_data.get("type") or last_event_type or "unknown")
            if event_type == "response.output_text.delta":
                delta_text = str(event_data.get("delta") or "")
                if delta_text:
                    accumulated_text += delta_text
            elif event_type == "response.output_text.done":
                done_text = str(event_data.get("text") or "")
                if done_text and not accumulated_text:
                    accumulated_text = done_text
            elif event_type == "response.completed":
                resp_data = event_data.get("response", event_data)
                self._raise_if_failed_response(resp_data)
                final_result = self._parse_response(resp_data)

        if final_result is not None:
            return final_result

        text = accumulated_text.strip()
        text_reasoning_content = None
        if text:
            text, text_reasoning_content = extract_text_reasoning_content(text)
        text_calls, text = parse_qwen_tool_calls(text or "")
        return GenerationResult(
            text=text if text else None,
            tool_calls=text_calls,
            finish_reason="stop",
            raw_response=raw_text,
            reasoning_content=build_reasoning_content(text=text_reasoning_content, origin_protocol="responses") if text_reasoning_content else None,
        )

    @staticmethod
    def _normalize_extra_params_for_responses(
        extra_params: Dict[str, Any],
        *,
        base_url: str,
        model: str,
    ) -> Dict[str, Any]:
        if not isinstance(extra_params, dict):
            return {}

        normalized = dict(extra_params)
        mutated_fields: List[str] = []

        # 主干说明：上层统一语义继续使用 thinking / reasoning / text 等通用字段。
        # 分支兼容：仅在本地 vLLM 路由上，将 thinking.disabled 改写为 enable_thinking=false，
        # 兼容当前 vLLM/Qwen 对“关闭思维链”的实际识别方式，避免业务层扩散供应商私有字段。
        thinking = normalized.get("thinking")
        if (
            ResponsesEmitter._is_local_vllm_base_url(base_url)
            and isinstance(thinking, dict)
            and str(thinking.get("type") or "").strip().lower() == "disabled"
        ):
            normalized.pop("thinking", None)
            normalized["enable_thinking"] = False
            mutated_fields.append("thinking.disabled->enable_thinking=false@local_vllm")

        developer_instruction: Optional[str] = None
        for key in RESPONSES_DEVELOPER_INSTRUCTION_KEYS:
            value = normalized.pop(key, None)
            if developer_instruction is None and isinstance(value, str) and value.strip():
                developer_instruction = value.strip()
                mutated_fields.append(f"{key}->instructions")

        for key in RESPONSES_TRANSPORT_CONTROL_KEYS:
            if key in normalized:
                normalized.pop(key, None)
                mutated_fields.append(f"drop:{key}")

        disable_store = normalized.pop("disable_response_storage", None)
        if disable_store is not None and "store" not in normalized:
            normalized["store"] = not bool(disable_store)
            mutated_fields.append("disable_response_storage->store")

        reasoning_effort = normalized.pop("model_reasoning_effort", None)
        if reasoning_effort is None:
            reasoning_effort = normalized.pop("reasoning_effort", None)
        if reasoning_effort is not None and "reasoning" not in normalized:
            normalized["reasoning"] = {"effort": str(reasoning_effort)}
            mutated_fields.append("*_reasoning_effort->reasoning.effort")

        model_verbosity = normalized.pop("model_verbosity", None)
        if model_verbosity is not None and "text" not in normalized:
            normalized["text"] = {"verbosity": str(model_verbosity)}
            mutated_fields.append("model_verbosity->text.verbosity")

        compat_reason = ResponsesEmitter._responses_compat_reason(base_url=base_url, model=model)
        if compat_reason == "ark_api_v3":
            # 主干：上层继续只表达通用语义（thinking / reasoning / text）。
            # 分支兼容：Ark /api/v3 当前会拒绝 OpenAI `text.verbosity`，
            # 但实际接受 `thinking={type:disabled}` 与 `reasoning.effort=minimal`。
            # 因此这里只裁掉已验证不兼容的 `text`，保留思维控制与工具链主干。
            if "text" in normalized:
                normalized.pop("text", None)
                mutated_fields.append("drop:text@ark_api_v3")

        # 主干：业务层继续表达通用 reasoning/thinking 语义。
        # 分支兼容：uni-grok 的 /responses 当前不接受显式 reasoningEffort，
        # 且关闭思维链也没有稳定的兼容字段，因此这里只裁掉显式控制，保留同一条 responses 主干。
        if ResponsesEmitter._is_uni_grok_responses_target(base_url=base_url, model=model):
            if "reasoning" in normalized:
                normalized.pop("reasoning", None)
                mutated_fields.append("drop:reasoning@uni_grok")
            if "thinking" in normalized:
                normalized.pop("thinking", None)
                mutated_fields.append("drop:thinking@uni_grok")

        if developer_instruction and "instructions" not in normalized:
            normalized["instructions"] = developer_instruction

        if mutated_fields:
            logger.info(
                "[responses][compat] normalized extra_params for /responses: "
                f"base_url={base_url} model={model} changes={','.join(mutated_fields)}"
            )

        return normalized

    @staticmethod
    def _build_stream_transport_timeout(
        total_timeout: float,
        *,
        idle_timeout: Optional[float] = None,
    ) -> httpx.Timeout:
        total = max(float(total_timeout or 0.0), 1.0)
        effective_idle_timeout = min(max(float(idle_timeout or 0.0), 1.0), total)
        return httpx.Timeout(
            connect=min(RESPONSES_CONNECT_TIMEOUT_SECONDS, total),
            write=min(RESPONSES_WRITE_TIMEOUT_SECONDS, total),
            read=effective_idle_timeout,
            pool=min(RESPONSES_POOL_TIMEOUT_SECONDS, total),
        )

    @staticmethod
    def _is_uni_qwen_non_stream_target(*, base_url: str, model: str) -> bool:
        raw = str(base_url or "").strip()
        if not raw:
            return False
        try:
            parsed = urlparse(raw)
        except ValueError:
            return False
        host = str(parsed.hostname or "").strip().lower()
        normalized_model = str(model or "").strip().lower()
        return host in UNI_QWEN_NON_STREAM_HOSTS and normalized_model in UNI_QWEN_NON_STREAM_MODELS

    @staticmethod
    def _payload_has_tool_continuation_items(payload: Dict[str, Any]) -> bool:
        for item in payload.get("input", []) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "") in {"function_call", "function_call_output"}:
                return True
        return False

    @staticmethod
    def _rewrite_uni_qwen_non_stream_tool_continuation(payload: Dict[str, Any]) -> bool:
        input_items = payload.get("input")
        if not isinstance(input_items, list) or not input_items:
            return False

        rewritten_items: List[Dict[str, Any]] = []
        tool_name_by_call_id: Dict[str, str] = {}
        mutated = False

        for item in input_items:
            if not isinstance(item, dict):
                rewritten_items.append(item)
                continue

            item_type = str(item.get("type") or "")
            if item_type == "function_call":
                mutated = True
                call_id = str(item.get("call_id") or item.get("id") or "")
                tool_name = str(item.get("name") or "tool")
                if call_id:
                    tool_name_by_call_id[call_id] = tool_name
                continue

            if item_type == "function_call_output":
                mutated = True
                call_id = str(item.get("call_id") or "")
                tool_name = tool_name_by_call_id.get(call_id, "tool")
                output = str(item.get("output") or "").strip() or "(空返回)"
                rewritten_items.append({
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": f"【工具 {tool_name} 返回】{output}",
                    }],
                })
                continue

            rewritten_items.append(item)

        if mutated:
            payload["input"] = rewritten_items
        return mutated

    @staticmethod
    def _build_request_url(base_url: str) -> str:
        return f"{base_url.rstrip('/')}/responses"

    @staticmethod
    def _build_request_headers(api_key: str, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def _generate_non_stream(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GenerationResult:
        url = self._build_request_url(base_url)
        tool_result_mode = self._select_tool_result_mode(base_url=base_url, model=request.model)

        payload = self._build_payload(
            request,
            base_url=base_url,
            tool_result_mode=tool_result_mode,
        )
        payload["stream"] = False
        # GPT routes reuse the same builder but receive route-only payload tuning
        # before the request is sent. Non-GPT routes are untouched here.
        self._apply_gpt_route_payload_compat(
            payload,
            base_url=base_url,
            model=request.model,
        )

        if self._is_uni_qwen_non_stream_target(base_url=base_url, model=request.model):
            mutated = self._rewrite_uni_qwen_non_stream_tool_continuation(payload)
            if mutated:
                logger.info(
                    "[responses][uni-qwen] rewritten tool continuation as tool results only: "
                    f"base_url={base_url} model={request.model}"
                )

        headers = self._build_request_headers(api_key, extra_headers)

        requested_timeout = float(timeout or 0.0)
        default_timeout = (
            UNI_QWEN_NON_STREAM_TIMEOUT_SECONDS
            if self._is_uni_qwen_non_stream_target(base_url=base_url, model=request.model)
            else RESPONSES_TOTAL_TIMEOUT_SECONDS
        )
        effective_timeout = (
            requested_timeout
            if requested_timeout > RESPONSES_TOTAL_TIMEOUT_SECONDS
            else default_timeout
        )

        logger.warning(
            "[responses][compat] forced non-stream transport: "
            f"url={url} model={request.model} timeout={effective_timeout}s"
        )

        _, dump_id = dump_prompt_request(protocol="responses", payload=payload)

        async with httpx.AsyncClient(
            proxy=proxy, timeout=effective_timeout, verify=False, trust_env=False
        ) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                body = resp.text[:1200]
                self._log_http_error(resp.status_code, url, body)
                raise RuntimeError(f"responses_http[{resp.status_code}]: {body}")

            content_type = str(resp.headers.get("content-type") or "").lower()
            raw_text = resp.text
            if "application/json" in content_type:
                data = resp.json()
                dump_prompt_response(protocol="responses", dump_id=dump_id, payload=data)
                self._raise_if_failed_response(data)
                return self._parse_response(data, dump_id=dump_id)

            logger.error(
                "[responses] unexpected non-json response from "
                f"{url}: content_type={content_type or 'unknown'} body={raw_text[:500]}"
            )
            raise RuntimeError(
                f"responses_unexpected_content_type[{content_type or 'unknown'}]: {raw_text[:500]}"
            )

    async def _consume_stream_transport(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
        emit_deltas: bool = False,
    ) -> AsyncGenerator[GenerationResult, None]:
        url = self._build_request_url(base_url)
        headers = self._build_request_headers(api_key, extra_headers)
        tool_result_mode = self._select_tool_result_mode(base_url=base_url, model=request.model)

        payload = self._build_payload(
            request,
            base_url=base_url,
            tool_result_mode=tool_result_mode,
        )
        payload["stream"] = True
        # Keep GPT payload adjustments local to GPT routes; other providers still
        # see the ordinary mainline `/responses` payload.
        self._apply_gpt_route_payload_compat(
            payload,
            base_url=base_url,
            model=request.model,
        )

        is_local_vllm_target = self._is_local_vllm_base_url(base_url)
        effective_total_timeout = (
            LOCAL_VLLM_RESPONSES_TIMEOUT_SECONDS
            if is_local_vllm_target
            else RESPONSES_TOTAL_TIMEOUT_SECONDS
        )
        configured_idle_timeout = _get_responses_stream_idle_timeout_seconds()
        effective_idle_timeout = (
            effective_total_timeout
            if is_local_vllm_target
            else min(configured_idle_timeout, effective_total_timeout)
        )

        logger.debug(
            f"[responses] POST {url} model={payload.get('model')} "
            f"input_items={len(payload.get('input', []))} "
            f"tools={len(payload.get('tools', []))} "
            f"stream_transport={payload.get('stream')} mode={tool_result_mode} "
            f"idle_timeout={effective_idle_timeout}s total_timeout={effective_total_timeout}s"
        )

        _, dump_id = dump_prompt_request(protocol="responses", payload=payload)
        started_at = time.monotonic()
        last_event_type = ""
        event_count = 0
        accumulated_text = ""
        final_result: Optional[GenerationResult] = None

        transport_timeout = self._build_stream_transport_timeout(
            effective_total_timeout,
            idle_timeout=effective_idle_timeout,
        )

        try:
            async with httpx.AsyncClient(
                proxy=proxy, timeout=transport_timeout, verify=False, trust_env=False
            ) as client:
                async with client.stream(
                    "POST", url, json=payload, headers=headers
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", errors="ignore")[:500]
                        self._log_http_error(resp.status_code, url, body)
                        raise RuntimeError(f"responses_http[{resp.status_code}]: {body}")

                    content_type = str(resp.headers.get("content-type") or "").lower()
                    if "text/event-stream" not in content_type:
                        body = await resp.aread()
                        body_text = body.decode("utf-8", errors="ignore")
                        data = json.loads(body_text)
                        dump_prompt_response(protocol="responses", dump_id=dump_id, payload=data)
                        self._raise_if_failed_response(data)
                        yield self._parse_response(data, dump_id=dump_id)
                        return

                    async for line in resp.aiter_lines():
                        elapsed = time.monotonic() - started_at
                        if elapsed > effective_total_timeout:
                            logger.error(
                                "[responses][timeout] stream total timeout exceeded: "
                                f"url={url} model={request.model} elapsed={elapsed:.1f}s "
                                f"event_count={event_count} last_event={last_event_type or 'none'}"
                            )
                            raise RuntimeError(
                                f"responses_stream_total_timeout[{effective_total_timeout:.1f}s]: "
                                f"last_event={last_event_type or 'none'} event_count={event_count}"
                            )

                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("event: "):
                            last_event_type = line[7:].strip()
                            continue

                        if not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            event_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event_type = str(event_data.get("type") or last_event_type or "unknown")
                        last_event_type = event_type
                        event_count += 1

                        if event_type == "response.output_text.delta":
                            delta_text = event_data.get("delta", "")
                            if delta_text:
                                accumulated_text += delta_text
                                if emit_deltas:
                                    yield GenerationResult(
                                        text=delta_text,
                                        finish_reason="",
                                    )

                        elif event_type == "response.output_text.done":
                            done_text = event_data.get("text", "")
                            if done_text and not accumulated_text:
                                accumulated_text = done_text

                        elif event_type == "response.completed":
                            resp_data = event_data.get("response", event_data)
                            dump_prompt_response(protocol="responses", dump_id=dump_id, payload=resp_data)
                            self._raise_if_failed_response(resp_data)
                            final_result = self._parse_response(resp_data, dump_id=dump_id)

        except httpx.ReadTimeout as exc:
            elapsed = time.monotonic() - started_at
            logger.error(
                "[responses][timeout] stream idle timeout exceeded: "
                f"url={url} model={request.model} idle_timeout={effective_idle_timeout:.1f}s "
                f"elapsed={elapsed:.1f}s event_count={event_count} last_event={last_event_type or 'none'}"
            )
            raise RuntimeError(
                f"responses_stream_idle_timeout[{effective_idle_timeout:.1f}s]: "
                f"last_event={last_event_type or 'none'} event_count={event_count}"
            ) from exc

        if final_result:
            yield final_result
        elif accumulated_text:
            text = accumulated_text
            text_reasoning_content = None
            if text:
                text, text_reasoning_content = extract_text_reasoning_content(text)
            text_calls, text = parse_qwen_tool_calls(text or "")
            yield GenerationResult(
                text=text if text and text.strip() else None,
                tool_calls=text_calls,
                finish_reason="stop",
                reasoning_content=build_reasoning_content(text=text_reasoning_content, origin_protocol="responses") if text_reasoning_content else None,
                dump_id=dump_id,
            )

    @staticmethod
    def _count_user_images(request: GenerationRequest) -> int:
        return sum(
            1
            for turn in request.messages
            if turn.role == "user"
            for part in turn.parts
            if part.type == "image"
        )

    @staticmethod
    def _is_local_vllm_base_url(base_url: str) -> bool:
        raw = str(base_url or "").strip()
        if not raw:
            return False
        try:
            parsed = urlparse(raw)
        except ValueError:
            return False
        host = str(parsed.hostname or "").strip().lower()
        return host in LOCAL_OPENAI_COMPAT_HOSTS

    @staticmethod
    def _select_image_max_long_edge(total_user_images: int, *, base_url: str = "") -> int:
        if ResponsesEmitter._is_local_vllm_base_url(base_url):
            return LOCAL_VLLM_FIXED_IMAGE_MAX_LONG_EDGE
        return VLLM_MAX_IMAGE_LONG_EDGE

    @staticmethod
    def _normalize_message_role(role: str) -> str:
        normalized = str(role or "").strip().lower()
        if normalized in RESPONSES_MESSAGE_ROLES:
            return normalized
        if normalized:
            logger.warning(
                "[responses][compat] unsupported message role for /responses, degraded to assistant: "
                f"role={normalized}"
            )
        return "assistant"

    @staticmethod
    def _build_tool_name_by_call_id(request: GenerationRequest) -> Dict[str, str]:
        tool_name_by_call_id: Dict[str, str] = {}
        for turn in request.messages:
            for tool_call in turn.tool_calls or []:
                if tool_call.id and tool_call.name:
                    tool_name_by_call_id[str(tool_call.id)] = str(tool_call.name)
        return tool_name_by_call_id

    @staticmethod
    def _select_tool_result_mode(*, base_url: str, model: str) -> str:
        return RESPONSES_TOOL_RESULT_MODE_NATIVE

    @staticmethod
    def _resolve_cache_control(cache_hints: Dict[str, str]) -> Optional[Dict[str, Any]]:
        raw = str((cache_hints or {}).get("cache_control") or "").strip().lower()
        if raw == "ephemeral":
            return dict(RESPONSES_GENERIC_CACHE_CONTROL)
        return None

    @staticmethod
    def _input_items_have_cache_control(input_items: List[Dict[str, Any]]) -> bool:
        for item in input_items:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for seg in content:
                if isinstance(seg, dict) and "cache_control" in seg:
                    return True
        return False

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _hash_json(value: Any) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _parse_int_cache_hint(cache_hints: Dict[str, str], key: str, default: int = -1) -> int:
        try:
            return int(str((cache_hints or {}).get(key) or "").strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _iter_cacheable_text_segments(input_items: List[Dict[str, Any]]):
        for input_index, item in enumerate(input_items):
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip().lower()
            if item_type != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_index, seg in enumerate(content):
                if not isinstance(seg, dict):
                    continue
                if str(seg.get("type") or "").strip().lower() != "input_text":
                    continue
                if str(seg.get("text") or ""):
                    yield input_index, content_index, seg

    @classmethod
    def _build_uni_grok_system_scope_digest(
        cls,
        *,
        payload: Dict[str, Any],
    ) -> str:
        input_items = payload.get("input") if isinstance(payload.get("input"), list) else []
        system_texts: List[str] = []
        for item in input_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() != "message":
                continue
            if str(item.get("role") or "").strip().lower() != "system":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for seg in content:
                if not isinstance(seg, dict):
                    continue
                if str(seg.get("type") or "").strip().lower() != "input_text":
                    continue
                text = str(seg.get("text") or "")
                if text:
                    system_texts.append(text)
        if not system_texts:
            return "nosystem"
        return cls._hash_json({"system_texts": system_texts})[:16]

    @classmethod
    def _build_uni_grok_prompt_cache_key(
        cls,
        *,
        context_id: str,
        model: str,
        system_scope_digest: str,
    ) -> str:
        normalized_scope = str(system_scope_digest or "").strip() or "nosystem"
        context_hash = cls._hash_text(str(context_id or ""))[:8] if context_id else "global"
        model_hash = cls._hash_text(str(model or ""))[:8]
        return f"hcz-uni-grok-{context_hash}-{model_hash}-{normalized_scope}"

    @staticmethod
    def _attach_cache_control_to_cacheable_text_segment(
        input_items: List[Dict[str, Any]],
        *,
        anchor_cacheable_index: int,
        cache_control: Dict[str, Any],
    ) -> bool:
        if anchor_cacheable_index < 0:
            return False
        cacheable_index = -1
        for _, _, seg in ResponsesEmitter._iter_cacheable_text_segments(input_items):
            cacheable_index += 1
            if cacheable_index != anchor_cacheable_index:
                continue
            if not isinstance(seg, dict):
                return False
            if str(seg.get("type") or "") != "input_text":
                return False
            seg.setdefault("cache_control", dict(cache_control))
            return True
        return False

    def _apply_uni_grok_prompt_cache_key_compat(
        self,
        payload: Dict[str, Any],
        *,
        context_id: str,
        base_url: str,
        model: str,
        cache_meta: Dict[str, Any],
    ) -> None:
        if not self._is_uni_grok_responses_target(base_url=base_url, model=model):
            return

        existing_key = str(payload.get("prompt_cache_key") or "").strip()
        prefix_hash = str((cache_meta or {}).get("prefix_hash") or "").strip()
        prefix_chars = int((cache_meta or {}).get("prefix_chars") or 0)
        strategy = str((cache_meta or {}).get("strategy") or "disabled")
        system_scope_digest = self._build_uni_grok_system_scope_digest(payload=payload)
        prompt_cache_key = existing_key or self._build_uni_grok_prompt_cache_key(
            context_id=context_id,
            model=model,
            system_scope_digest=system_scope_digest,
        )
        key_source = "existing" if existing_key else "system_scope"

        stripped_top_level = self._strip_top_level_cache_control_in_place(payload)
        stripped_content = self._strip_content_cache_control_in_place(payload)

        if prompt_cache_key:
            payload["prompt_cache_key"] = prompt_cache_key
            logger.info(
                "[responses][uni_grok][cache] mapped generic cache mainline to prompt_cache_key: "
                f"context_id={context_id or ''} base_url={base_url} model={model} strategy={strategy} "
                f"prefix_hash={prefix_hash or '-'} prefix_chars={prefix_chars} system_scope_digest={system_scope_digest} "
                f"key_source={key_source} prompt_cache_key={prompt_cache_key} "
                f"stripped_top_level={stripped_top_level} stripped_content={stripped_content}"
            )
            return

        if stripped_top_level or stripped_content:
            logger.info(
                "[responses][uni_grok][cache] dropped inert cache_control without prompt_cache_key: "
                f"context_id={context_id or ''} base_url={base_url} model={model} strategy={strategy} "
                f"prefix_hash={prefix_hash or '-'} prefix_chars={prefix_chars} system_scope_digest={system_scope_digest} "
                f"stripped_top_level={stripped_top_level} stripped_content={stripped_content}"
            )

    def _apply_generic_cache_control_to_payload(
        self,
        payload: Dict[str, Any],
        *,
        context_id: str,
        base_url: str,
        model: str,
        cache_hints: Dict[str, str],
    ) -> Dict[str, Any]:
        """Translate router canonical cache prefix hints into `/responses` cache_control.

        Mainline:
            Router owns canonical LCP calculation after media policy is finalized.
            The `/responses` emitter only maps the router-selected cacheable text
            segment onto provider wire format.

        Branch compatibility:
            Provider-specific branches may add request-shape compatibility on top of
            this result, but they must not replace this function with a separate
            parallel mainline.
        """
        bypass_reason = self._responses_compat_reason(base_url=base_url, model=model)
        if bypass_reason:
            logger.info(
                "[responses][cache] bypass generic cache control for compatibility target: "
                f"reason={bypass_reason} context_id={context_id or ''} base_url={base_url} model={model}"
            )
            return {
                "snapshot_state": f"{bypass_reason}_bypass",
                "strategy": f"disabled_for_{bypass_reason}",
                "attached": False,
                "unit_count": 0,
                "lcp_unit_count": 0,
                "anchor_input_index": -1,
                "anchor_content_index": -1,
                "prefix_hash": "",
                "prefix_chars": 0,
            }

        cache_control = ResponsesEmitter._resolve_cache_control(cache_hints)
        if not cache_control:
            return {
                "snapshot_state": "cache_disabled",
                "strategy": "disabled",
                "attached": False,
                "unit_count": 0,
                "lcp_unit_count": 0,
                "anchor_input_index": -1,
                "anchor_content_index": -1,
                "prefix_hash": "",
                "prefix_chars": 0,
            }

        input_items = payload.get("input") if isinstance(payload.get("input"), list) else []
        if not input_items:
            return {
                "snapshot_state": "empty_input",
                "strategy": "top_level_only",
                "attached": False,
                "unit_count": 0,
                "lcp_unit_count": 0,
                "anchor_input_index": -1,
                "anchor_content_index": -1,
                "prefix_hash": "",
                "prefix_chars": 0,
            }

        payload.setdefault("cache_control", dict(cache_control))
        if self._input_items_have_cache_control(input_items):
            return {
                "snapshot_state": "existing_content_cache_control",
                "strategy": "existing_content_block",
                "attached": True,
                "unit_count": 0,
                "lcp_unit_count": 0,
                "anchor_input_index": -1,
                "anchor_content_index": -1,
                "prefix_hash": "",
                "prefix_chars": 0,
            }

        anchor_cacheable_index = self._parse_int_cache_hint(cache_hints, "stable_prefix_anchor_cacheable_index")
        lcp_unit_count = self._parse_int_cache_hint(cache_hints, "stable_prefix_units", 0)
        prefix_hash = str((cache_hints or {}).get("stable_prefix_hash") or "")
        prefix_chars = self._parse_int_cache_hint(cache_hints, "stable_prefix_chars", 0)
        strategy = "router_canonical_lcp" if anchor_cacheable_index >= 0 else "top_level_only"
        attached = self._attach_cache_control_to_cacheable_text_segment(
            input_items,
            anchor_cacheable_index=anchor_cacheable_index,
            cache_control=cache_control,
        )
        if not attached:
            strategy = "top_level_only"

        logger.info(
            "[responses][cache] router canonical cache control applied: "
            f"context_id={context_id or ''} base_url={base_url} model={model} "
            f"snapshot_state={str((cache_hints or {}).get('stable_prefix_snapshot') or '')} "
            f"strategy={strategy} attached={attached} "
            f"lcp_unit_count={lcp_unit_count} anchor_cacheable_index={anchor_cacheable_index} "
            f"prefix_hash={prefix_hash or '-'} prefix_chars={prefix_chars}"
        )
        return {
            "snapshot_state": str((cache_hints or {}).get("stable_prefix_snapshot") or ""),
            "strategy": strategy,
            "attached": attached,
            "unit_count": 0,
            "lcp_unit_count": lcp_unit_count,
            "anchor_input_index": -1,
            "anchor_content_index": -1,
            "prefix_hash": prefix_hash,
            "prefix_chars": prefix_chars,
        }

    @staticmethod
    def _build_data_uri(mime_type: str, data: bytes) -> str:
        mime = str(mime_type or "application/octet-stream").strip() or "application/octet-stream"
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    @staticmethod
    def _parse_data_uri(uri: str) -> Optional[tuple[str, bytes]]:
        if not isinstance(uri, str) or not uri.startswith("data:") or "," not in uri:
            return None
        header, payload = uri.split(",", 1)
        mime_type = header[5:].split(";", 1)[0].strip() or "application/octet-stream"
        try:
            if ";base64" in header.lower():
                return mime_type, base64.b64decode(payload, validate=True)
            return mime_type, payload.encode("utf-8")
        except (ValueError, binascii.Error):
            return None

    @staticmethod
    def _normalize_image_bytes_for_vllm(
        *,
        mime_type: str,
        data: bytes,
        source: str,
        max_long_edge: int = VLLM_MAX_IMAGE_LONG_EDGE,
    ) -> tuple[str, bytes]:
        mime = str(mime_type or "image/png").strip().lower() or "image/png"
        if not mime.startswith("image/") or not data:
            return mime_type, data

        try:
            with Image.open(io.BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image)
                width, height = image.size
                if max(width, height) <= max_long_edge:
                    if mime == "image/jpg":
                        return "image/jpeg", data
                    return mime_type, data

                resized = image.copy()
                resized.thumbnail((max_long_edge, max_long_edge), Image.Resampling.LANCZOS)
                new_width, new_height = resized.size

                has_alpha = "A" in resized.getbands() or "transparency" in resized.info
                output = io.BytesIO()
                if has_alpha:
                    output_mime = "image/png"
                    resized.save(output, format="PNG")
                else:
                    output_mime = "image/jpeg"
                    if resized.mode not in {"RGB", "L"}:
                        resized = resized.convert("RGB")
                    resized.save(output, format="JPEG", quality=90, optimize=True)

                normalized = output.getvalue()
                logger.info(
                    "[responses][image] normalized oversized image for vLLM: "
                    f"source={source} size={width}x{height} -> {new_width}x{new_height} "
                    f"mime={mime} -> {output_mime} bytes={len(data)} -> {len(normalized)}"
                )
                return output_mime, normalized
        except Exception as exc:
            logger.warning(
                "[responses][image] normalize oversized image failed, keep original: "
                f"source={source} mime={mime} err={exc}"
            )
            return mime_type, data

    @staticmethod
    def _raise_if_failed_response(data: Dict[str, Any]) -> None:
        """将 responses 的 failed/error 响应显式抛出，避免被误判为空结果。"""
        status = str(data.get("status") or "").strip().lower()
        error = data.get("error") if isinstance(data.get("error"), dict) else {}
        if status != "failed" and not error:
            return

        code = str(error.get("code") or "responses_failed")
        message = str(error.get("message") or "responses request failed")
        raise RuntimeError(f"responses_failed[{code}]: {message}")

    @staticmethod
    def _log_http_error(status_code: int, url: str, body: str) -> None:
        """安全记录上游 HTTP 错误，避免原始 JSON 花括号干扰日志格式化。"""
        try:
            logger.error("[responses] {} from {}: {}", status_code, url, body)
        except Exception as log_error:
            logger.error(
                "[responses] http error logging failed: status={} url={} body_len={} type={} err={!r}",
                status_code,
                url,
                len(str(body or "")),
                type(log_error).__name__,
                log_error,
            )

    # ── IR → wire format ──

    def _build_payload(
        self,
        request: GenerationRequest,
        *,
        base_url: str = "",
        tool_result_mode: str = RESPONSES_TOOL_RESULT_MODE_NATIVE,
    ) -> Dict[str, Any]:
        """将 GenerationRequest 转为 /responses 请求体"""
        input_items: List[Dict[str, Any]] = []
        total_user_images = self._count_user_images(request)
        image_max_long_edge = self._select_image_max_long_edge(total_user_images, base_url=base_url)
        if image_max_long_edge != VLLM_MAX_IMAGE_LONG_EDGE:
            logger.info(
                "[responses][image] apply local vllm fixed image budget: "
                f"user_images={total_user_images} max_long_edge={image_max_long_edge} "
                f"base_url={base_url}"
            )

        normalized_messages = self._merge_leading_system_turns(request.messages)
        tool_name_by_call_id = self._build_tool_name_by_call_id(request)
        replay_reasoning_content = bool(
            isinstance(request.extra_params, dict)
            and request.extra_params.get("replay_reasoning_content")
        )
        for turn in normalized_messages:
            items = self._turn_to_input_items(
                turn,
                image_max_long_edge=image_max_long_edge,
                tool_result_mode=tool_result_mode,
                tool_name_by_call_id=tool_name_by_call_id,
                replay_reasoning_content=replay_reasoning_content,
            )
            input_items.extend(items)

        payload: Dict[str, Any] = {
            "model": request.model,
            "input": input_items,
            "stream": request.stream,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_output_tokens"] = request.max_tokens

        # tools (responses 格式)
        if request.tools:
            payload["tools"] = [self._spec_to_tool(s) for s in request.tools]

        if request.extra_params:
            payload.update(self._normalize_extra_params_for_responses(
                request.extra_params,
                base_url=base_url,
                model=request.model,
            ))

        if self._is_gpt_responses_relay_target(base_url=base_url, model=request.model):
            rewritten = self._rewrite_gpt_relay_assistant_input_text_in_place(payload)
            if rewritten:
                logger.info(
                    "[responses][gpt] relay payload adjusted: assistant input_text -> output_text "
                    f"base_url={base_url} model={request.model} segments={rewritten}"
                )

        cache_meta = self._apply_generic_cache_control_to_payload(
            payload,
            context_id=request.context_id,
            base_url=base_url,
            model=request.model,
            cache_hints=request.cache_hints,
        )
        self._apply_uni_grok_prompt_cache_key_compat(
            payload,
            context_id=request.context_id,
            base_url=base_url,
            model=request.model,
            cache_meta=cache_meta,
        )

        return payload

    @staticmethod
    def _parse_replay_reasoning_items(reasoning_content: Optional[str]) -> List[Dict[str, Any]]:
        return get_responses_reasoning_items(reasoning_content)

    @staticmethod
    def _parse_replay_text_reasoning(reasoning_content: Optional[str]) -> Optional[str]:
        if get_responses_reasoning_items(reasoning_content):
            return None
        return get_text_reasoning_content(reasoning_content)

    @staticmethod
    def _inject_text_reasoning_content(content: List[Dict[str, Any]], reasoning_content: Optional[str]) -> List[Dict[str, Any]]:
        rendered = format_text_reasoning_for_history(reasoning_content)
        if not rendered:
            return content
        updated = [dict(item) for item in content]
        for item in updated:
            if item.get("type") == "input_text":
                item["text"] = format_text_reasoning_for_history(reasoning_content, str(item.get("text") or ""))
                return updated
        return [{"type": "input_text", "text": rendered}, *updated]

    @staticmethod
    def _extract_reasoning_items(output: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [dict(item) for item in output if isinstance(item, dict) and item.get("type") == "reasoning"]

    def _tool_result_parts_to_output_text(self, parts: List[MessagePart]) -> str:
        text_output = self._text_parts_to_string(parts).strip()
        if text_output:
            return text_output

        previews: List[str] = []
        for part in parts:
            if part.type == "image":
                previews.append(f"[图片结果] {part.url or ''}".strip())
            elif part.type == "audio":
                previews.append(f"[音频结果] {part.url or ''}".strip())
            elif part.type == "video":
                previews.append(f"[视频结果] {part.url or ''}".strip())
            elif part.type == "file":
                previews.append(f"[文件结果] {part.url or ''}".strip())
            elif part.type == "text" and part.text:
                previews.append(part.text.strip())

        preview_text = "\n".join([item for item in previews if item]).strip()
        return preview_text or "(空返回)"

    def _tool_turn_to_input_items(
        self,
        turn: MessageTurn,
        *,
        image_max_long_edge: int = VLLM_MAX_IMAGE_LONG_EDGE,
        tool_result_mode: str = RESPONSES_TOOL_RESULT_MODE_NATIVE,
        tool_name_by_call_id: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        text_output = self._tool_result_parts_to_output_text(turn.parts)

        if turn.tool_call_id:
            return [{
                "type": "function_call_output",
                "call_id": turn.tool_call_id,
                "output": text_output,
            }]

        logger.warning(
            "[responses][compat] tool history missing tool_call_id after history backfill, degraded to assistant text"
        )
        content = self._parts_to_content(
            turn.parts,
            role="assistant",
            image_max_long_edge=image_max_long_edge,
        )
        if not content:
            return []
        return [{
            "type": "message",
            "role": "assistant",
            "content": content,
        }]

    def _turn_to_input_items(
        self,
        turn: MessageTurn,
        *,
        image_max_long_edge: int = VLLM_MAX_IMAGE_LONG_EDGE,
        tool_result_mode: str = RESPONSES_TOOL_RESULT_MODE_NATIVE,
        tool_name_by_call_id: Optional[Dict[str, str]] = None,
        replay_reasoning_content: bool = False,
    ) -> List[Dict[str, Any]]:
        """MessageTurn → list of responses input items (always returns list)"""
        if turn.role == "tool":
            return self._tool_turn_to_input_items(
                turn,
                image_max_long_edge=image_max_long_edge,
                tool_result_mode=tool_result_mode,
                tool_name_by_call_id=tool_name_by_call_id,
            )

        # assistant with tool_calls
        if turn.role == "assistant" and turn.tool_calls:
            items: List[Dict[str, Any]] = []
            # 主干：模型组 REPLAY_REASONING_CONTENT 决定是否回放隐藏思考。
            # 分支兼容：Responses 的隐藏思考是 output 中的 reasoning item，不是 chat 的 reasoning_content 字段。
            text_reasoning_content = None
            if replay_reasoning_content:
                items.extend(self._parse_replay_reasoning_items(turn.reasoning_content))
                text_reasoning_content = self._parse_replay_text_reasoning(turn.reasoning_content)
            # 如果有文本内容
            text = self._text_parts_to_string(turn.parts)
            if text_reasoning_content or text:
                rendered_text = format_text_reasoning_for_history(text_reasoning_content, text)
                items.append({
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "input_text", "text": rendered_text}],
                })
            for tc in turn.tool_calls:
                call_item = {
                    "type": "function_call",
                    "call_id": tc.id,
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                }
                responses_item_id = str((getattr(tc, "meta", {}) or {}).get("responses_item_id") or "").strip()
                if responses_item_id:
                    call_item["id"] = responses_item_id
                items.append(call_item)
            return items

        # Regular message
        role = self._normalize_message_role(turn.role)
        content = self._parts_to_content(turn.parts, role=role, image_max_long_edge=image_max_long_edge)
        replay_items: List[Dict[str, Any]] = []
        if role == "assistant" and replay_reasoning_content:
            replay_items.extend(self._parse_replay_reasoning_items(turn.reasoning_content))
            text_reasoning_content = self._parse_replay_text_reasoning(turn.reasoning_content)
            if text_reasoning_content:
                content = self._inject_text_reasoning_content(content, text_reasoning_content)
        if not content:
            return replay_items

        return [
            *replay_items,
            {
                "type": "message",
                "role": role,
                "content": content,
            },
        ]

    def _parts_to_content(
        self,
        parts: List[MessagePart],
        role: str = "user",
        *,
        image_max_long_edge: int = VLLM_MAX_IMAGE_LONG_EDGE,
    ) -> List[Dict[str, Any]]:
        """MessagePart 列表 → responses content 数组"""
        content: List[Dict[str, Any]] = []
        for part in parts:
            if part.type == "text":
                if part.text:
                    content.append({"type": "input_text", "text": part.text})
            elif part.type == "image":
                if role == "assistant":
                    continue
                if role != "user":
                    fname = (part.url or "image").rsplit("/", 1)[-1]
                    content.append({"type": "input_text", "text": f"[历史图片: {fname}]"})
                    continue
                image_url = self._resolve_image_url(part, max_long_edge=image_max_long_edge)
                if image_url:
                    content.append({
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": part.detail,
                    })
                else:
                    # 图片无法解析为有效 URL → 降级为文本描述
                    fname = (part.url or "image").rsplit("/", 1)[-1]
                    content.append({"type": "input_text", "text": f"[图片: {fname}]"})
            else:
                # audio/video/file → degrade
                degraded = self._degrade_media_part(part)
                if degraded.text:
                    content.append({"type": "input_text", "text": degraded.text})
        return content

    @staticmethod
    def _resolve_image_url(part: MessagePart, *, max_long_edge: int = VLLM_MAX_IMAGE_LONG_EDGE) -> Optional[str]:
        """将 MessagePart 的图片数据解析为 data URI 或 URL

        Returns None if the image can't be resolved to a valid URL.
        """
        if part.data:
            mime = part.mime_type or "image/png"
            mime, data = ResponsesEmitter._normalize_image_bytes_for_vllm(
                mime_type=mime,
                data=part.data,
                source="inline-bytes",
                max_long_edge=max_long_edge,
            )
            return ResponsesEmitter._build_data_uri(mime, data)
        if part.url:
            if part.url.startswith("data:"):
                parsed = ResponsesEmitter._parse_data_uri(part.url)
                if not parsed:
                    return part.url
                mime, data = parsed
                mime, data = ResponsesEmitter._normalize_image_bytes_for_vllm(
                    mime_type=mime,
                    data=data,
                    source="data-uri",
                    max_long_edge=max_long_edge,
                )
                return ResponsesEmitter._build_data_uri(mime, data)
            # HTTP(S) URL → 直接使用
            if part.url.startswith(("http://", "https://")):
                return part.url
            # 本地绝对路径 → 尝试转为 data URI
            if part.url.startswith("/") and Path(part.url).exists():
                try:
                    path = Path(part.url)
                    if path.stat().st_size > 10 * 1024 * 1024:  # 10MB 限制
                        return None
                    mime = mimetypes.guess_type(str(path))[0] or "image/png"
                    mime, data = ResponsesEmitter._normalize_image_bytes_for_vllm(
                        mime_type=mime,
                        data=path.read_bytes(),
                        source=str(path),
                        max_long_edge=max_long_edge,
                    )
                    return ResponsesEmitter._build_data_uri(mime, data)
                except Exception:
                    return None
            # 其他格式（相对路径、历史虚拟路径等）→ 无法解析
            return None
        return None

    @staticmethod
    def _spec_to_tool(spec: ToolSpec) -> Dict[str, Any]:
        """ToolSpec → responses tool 定义"""
        return {
            "type": "function",
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        }

    # ── wire format → IR ──

    def _parse_response(self, data: Dict[str, Any], *, dump_id: Optional[str] = None) -> GenerationResult:
        """responses 完整响应 → GenerationResult

        只取 message -> content -> output_text（按文档推荐）
        """
        output = data.get("output", [])

        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []
        reasoning_items = self._extract_reasoning_items(output)
        reasoning_content = build_reasoning_content(
            responses_items=reasoning_items,
            origin_protocol="responses" if reasoning_items else "",
        )

        for item in output:
            item_type = item.get("type", "")

            if item_type == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text_parts.append(content.get("text", ""))

            elif item_type == "function_call":
                args_str = item.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {"raw": args_str}
                item_id = str(item.get("id") or "").strip()
                call_id = str(item.get("call_id") or item_id or f"call_{uuid.uuid4().hex[:8]}")
                meta = {"responses_item_id": item_id} if item_id else {}
                tool_calls.append(ToolCall(
                    id=call_id,
                    name=item.get("name", ""),
                    arguments=args if isinstance(args, dict) else {},
                    meta=meta,
                ))

        text = "".join(text_parts) if text_parts else None
        text_reasoning_content = None
        if text:
            text, text_reasoning_content = extract_text_reasoning_content(text)
        if text_reasoning_content or reasoning_items:
            reasoning_content = build_reasoning_content(
                text=text_reasoning_content,
                responses_items=reasoning_items,
                origin_protocol="responses",
            )

        # Qwen 兼容：从可见文本中提取 tool_call
        text_extracted: List[ToolCall] = []
        if text:
            text_extracted, text = parse_qwen_tool_calls(text)

        all_calls = merge_tool_calls(
            tool_calls if tool_calls else None,
            text_extracted,
        )

        return GenerationResult(
            text=text if text and text.strip() else None,
            tool_calls=all_calls,
            finish_reason=data.get("status", "completed"),
            usage=data.get("usage"),
            raw_response=data,
            reasoning_content=reasoning_content,
            dump_id=dump_id,
        )

    # ── 实际网络调用 ──

    async def generate(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GenerationResult:
        """非流式 /responses 调用

        实现上内部统一走 stream transport：
        - 只要 SSE 仍有事件流入，就持续等待
        - 按配置的空闲超时秒数判定 idle timeout
        - 对上层仍返回最终完整 GenerationResult
        """
        if self._is_uni_qwen_non_stream_target(base_url=base_url, model=request.model):
            return await self._generate_non_stream(
                request,
                api_key=api_key,
                base_url=base_url,
                proxy=proxy,
                timeout=timeout,
                extra_headers=extra_headers,
            )

        final_result: Optional[GenerationResult] = None
        async for chunk in self._consume_stream_transport(
            request,
            api_key=api_key,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout,
            extra_headers=extra_headers,
            emit_deltas=False,
        ):
            final_result = chunk

        if final_result is None:
            raise RuntimeError("responses_stream_empty_result")
        return final_result

    async def generate_stream(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[GenerationResult, None]:
        """流式 /responses 调用

        容忍策略（按文档）：
        - delta 优先，final fallback
        - 个别事件缺失时不影响最终结果提取
        """
        if self._is_uni_qwen_non_stream_target(base_url=base_url, model=request.model):
            yield await self._generate_non_stream(
                request,
                api_key=api_key,
                base_url=base_url,
                proxy=proxy,
                timeout=timeout,
                extra_headers=extra_headers,
            )
            return

        emitted = False
        async for chunk in self._consume_stream_transport(
            request,
            api_key=api_key,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout,
            extra_headers=extra_headers,
            emit_deltas=True,
        ):
            emitted = True
            yield chunk

        if not emitted:
            raise RuntimeError("responses_stream_empty_result")
