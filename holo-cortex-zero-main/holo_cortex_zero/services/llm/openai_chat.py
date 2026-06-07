"""OpenAI chat.completions 协议发射器

处理：
- 标准 OpenAI API
- 所有 OpenAI-compatible 网关（vLLM chat.completions, Deepseek, etc.）
- 辅助 LLM 调用（timeline, subconscious, mem0）
"""
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
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
from .reasoning_text import extract_text_reasoning_content, get_text_reasoning_content, merge_reasoning_content


CHAT_TRANSPORT_CONTROL_KEYS = {
    "__transport",
    "_transport",
    "transport",
    "api_mode",
    "wire_api",
    "force_stream",
    "force_stream_mode",
    "skip_native_tools",
    MODEL_GROUP_CACHE_TRANSPORT_PROFILE_EXTRA_KEY,
}
CHAT_GENERIC_CACHE_CONTROL = {"type": "ephemeral"}
CHAT_CONTENT_CACHE_COMPAT_HOSTS = set(UNIAPI_HOSTS)
DEEPSEEK_OFFICIAL_CHAT_HOSTS = {"api.deepseek.com"}
DEEPSEEK_OFFICIAL_CACHE_TRANSPORT_FIELD_KEYS = (
    "cache_control",
    "prompt_cache_key",
    "prompt_cache_retention",
    "cache_prompt",
)
CHAT_INTERNAL_REASONING_CONTENT_KEY = "__hcz_reasoning_content"
CHAT_REPLAY_REASONING_CONTENT_KEY = "replay_reasoning_content"
LOCAL_OPENAI_COMPAT_HOSTS = {
    "127.0.0.1",
    "::1",
    "localhost",
    "host.docker.internal",
    "172.19.0.1",
}


class OpenAIChatEmitter(BaseEmitter):
    """chat.completions 协议发射器"""

    def get_media_capabilities(self) -> EmitterMediaCapabilities:
        return EmitterMediaCapabilities(
            name="openai_chat",
            accepts_image_parts=True,
            accepts_audio_parts=False,
            accepts_video_parts=False,
            native_tool_calling=True,
            notes="chat.completions 当前仅原生接收图片；音频/视频/文件在发射器内降级为文本。",
        )

    # ── IR → wire format ──

    def _build_payload(self, request: GenerationRequest) -> Dict[str, Any]:
        """将 GenerationRequest 转为 chat.completions 请求体"""
        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": [self._turn_to_message(t, request=request) for t in request.messages],
            "stream": request.stream,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        # tools
        if request.tools:
            # 如果 extra_params 中指定了 skip_native_tools，
            # 不发送 tools/tool_choice（让模型通过文本输出 tool_call）
            if not request.extra_params.get("skip_native_tools"):
                payload["tools"] = [self._spec_to_function(s) for s in request.tools]
                # 不强制 tool_choice=auto，有些后端不支持
                # payload["tool_choice"] = "auto"

        return payload

    @staticmethod
    def _parse_base_url(base_url: str) -> tuple[str, int | None]:
        raw = str(base_url or "").strip()
        if not raw:
            return "", None
        try:
            parsed = httpx.URL(raw)
        except Exception:
            return "", None
        return str(parsed.host or "").strip().lower(), parsed.port

    @classmethod
    def _is_local_vllm_chat_target(cls, *, base_url: str) -> bool:
        host, _ = cls._parse_base_url(base_url)
        return host in LOCAL_OPENAI_COMPAT_HOSTS

    @classmethod
    def _is_content_cache_compat_target(cls, *, base_url: str) -> bool:
        host, _ = cls._parse_base_url(base_url)
        return host in CHAT_CONTENT_CACHE_COMPAT_HOSTS

    @classmethod
    def _is_deepseek_official_chat_target(cls, *, base_url: str) -> bool:
        """DeepSeek 官方 chat.completions 分支。"""
        host, _ = cls._parse_base_url(base_url)
        return host in DEEPSEEK_OFFICIAL_CHAT_HOSTS

    @staticmethod
    def _resolve_cache_control(cache_hints: Dict[str, str]) -> Optional[Dict[str, Any]]:
        raw = str((cache_hints or {}).get("cache_control") or "").strip().lower()
        if raw == "ephemeral":
            return dict(CHAT_GENERIC_CACHE_CONTROL)
        return None

    @staticmethod
    def _hash_json(value: Any) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _cache_transport_profile(request: GenerationRequest) -> str:
        raw = ""
        if isinstance(request.extra_params, dict):
            raw = str(request.extra_params.get(MODEL_GROUP_CACHE_TRANSPORT_PROFILE_EXTRA_KEY) or "").strip().lower()
        if raw in {"", "default", "auto", "none"}:
            return "default"
        if raw in {"cache_control", "cache-control", "anthropic"}:
            return "cache_control"
        if raw in {"prompt_cache_key", "prompt-cache-key", "openai"}:
            return "prompt_cache_key"
        if raw in {"cache_prompt", "cache-prompt", "local"}:
            return "cache_prompt"
        if raw in {"off", "disabled", "disable", "none"}:
            return "off"
        logger.warning(
            "[openai_chat][cache] unknown CACHE_TRANSPORT_PROFILE, fallback default: "
            f"value={raw} model={request.model} context_id={request.context_id or ''}"
        )
        return "default"

    @classmethod
    def _build_prompt_cache_key(cls, request: GenerationRequest, *, base_url: str) -> str:
        host, _ = cls._parse_base_url(base_url)
        return "hcz-chat-" + cls._hash_json({
            "context_id": str(request.context_id or ""),
            "host": host,
            "model": str(request.model or ""),
        })[:32]

    @classmethod
    def _build_deepseek_official_cache_partition_user_id(
        cls,
        request: GenerationRequest,
        *,
        base_url: str,
    ) -> str:
        host, _ = cls._parse_base_url(base_url)
        cache_domain = str((request.cache_hints or {}).get("cache_domain") or "").strip()
        context_id = str(request.context_id or "").strip() or "global"
        return "hcz-ds-" + cls._hash_json({
            "host": host,
            "model": str(request.model or "").strip(),
            "context_id": context_id,
            "cache_domain": cache_domain,
        })[:40]

    @staticmethod
    def _message_has_cache_control(message: Dict[str, Any]) -> bool:
        content = message.get("content")
        if not isinstance(content, list):
            return False
        for seg in content:
            if isinstance(seg, dict) and "cache_control" in seg:
                return True
        return False

    @classmethod
    def _messages_have_cache_control(cls, messages: List[Dict[str, Any]]) -> bool:
        return any(cls._message_has_cache_control(message) for message in messages if isinstance(message, dict))

    @classmethod
    def _apply_cache_hints_to_payload(
        cls,
        payload: Dict[str, Any],
        *,
        request: GenerationRequest,
        base_url: str,
    ) -> None:
        cache_control = cls._resolve_cache_control(request.cache_hints)
        if not cache_control:
            return
        if cls._is_deepseek_official_chat_target(base_url=base_url):
            logger.info(
                "[openai_chat][cache][deepseek_official] ignored explicit cache transport profile: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''} "
                f"reason=deepseek_context_cache_is_automatic cache_hints={dict(request.cache_hints)}"
            )
            return
        profile = cls._cache_transport_profile(request)
        if profile == "off":
            logger.info(
                "[openai_chat][cache] explicit cache disabled by model group: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''}"
            )
            return

        messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
        if not messages:
            logger.info(
                "[openai_chat][cache] skipped cache hint application: "
                f"reason=empty_messages base_url={base_url} model={request.model} "
                f"context_id={request.context_id or ''}"
            )
            return

        if profile == "prompt_cache_key":
            payload.setdefault("prompt_cache_key", cls._build_prompt_cache_key(request, base_url=base_url))
            payload.setdefault("prompt_cache_retention", "24h")
            logger.info(
                "[openai_chat][cache] applied prompt cache key by model group: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''} "
                f"profile={profile} prompt_cache_key={payload.get('prompt_cache_key')}"
            )
            return

        if profile == "cache_prompt":
            payload["cache_prompt"] = True
            logger.info(
                "[openai_chat][cache] enabled cache_prompt by model group: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''}"
            )
            return

        if cls._messages_have_cache_control(messages):
            logger.info(
                "[openai_chat][cache] preserved existing content cache control: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''}"
            )
            return

        if "cache_control" in payload:
            logger.info(
                "[openai_chat][cache] preserved existing top-level cache control: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''}"
            )
            return

        if profile == "default" and cls._is_local_vllm_chat_target(base_url=base_url):
            payload["cache_prompt"] = True
            logger.info(
                "[openai_chat][cache][local_chat] enabled prompt cache: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''} "
                f"cache_hints={dict(request.cache_hints)}"
            )
            return

        if profile == "default" and cls._is_content_cache_compat_target(base_url=base_url):
            logger.info(
                "[openai_chat][cache] content-cache compatibility branch disabled by default: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''} "
                f"cache_hints={dict(request.cache_hints)}"
            )
            return

        if profile not in {"default", "cache_control"}:
            logger.info(
                "[openai_chat][cache] skipped generic cache_control for default chat target: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''} "
                f"profile={profile} cache_hints={dict(request.cache_hints)}"
            )
            return

        # 主干：cache_hints 仍是框架统一入口；模型组 profile 决定 chat wire 格式。
        # 分支兼容：default/openai/local/off 在上方提前返回，避免一条供应商分支变成并行主干。
        payload["cache_control"] = dict(cache_control)
        logger.info(
            "[openai_chat][cache] applied generic top-level cache_control: "
            f"base_url={base_url} model={request.model} context_id={request.context_id or ''} "
            f"cache_hints={dict(request.cache_hints)}"
        )
        return

    @classmethod
    def _normalize_extra_params_for_chat(
        cls,
        extra_params: Dict[str, Any],
        *,
        base_url: str,
        model: str,
        has_tools: bool = False,
    ) -> Dict[str, Any]:
        if not isinstance(extra_params, dict):
            extra_params = {}

        normalized = dict(extra_params)
        mutated_fields: List[str] = []

        thinking = normalized.get("thinking")
        if (
            cls._is_local_vllm_chat_target(base_url=base_url)
            and isinstance(thinking, dict)
            and str(thinking.get("type") or "").strip().lower() == "disabled"
        ):
            normalized.pop("thinking", None)
            chat_template_kwargs = (
                dict(normalized.get("chat_template_kwargs") or {})
                if isinstance(normalized.get("chat_template_kwargs"), dict)
                else {}
            )
            chat_template_kwargs["enable_thinking"] = False
            normalized["chat_template_kwargs"] = chat_template_kwargs
            mutated_fields.append("thinking.disabled->chat_template_kwargs.enable_thinking=false@local_vllm_chat")

        if cls._is_deepseek_official_chat_target(base_url=base_url):
            cls._normalize_deepseek_official_extra_params_in_place(
                normalized,
                mutated_fields=mutated_fields,
            )
            if has_tools and str(normalized.get("tool_choice") or "").strip().lower() == "required":
                normalized.pop("tool_choice", None)
                mutated_fields.append("drop:tool_choice.required@deepseek_official_tools")

        for key in CHAT_TRANSPORT_CONTROL_KEYS:
            if key in normalized:
                normalized.pop(key, None)
                mutated_fields.append(f"drop:{key}")

        if mutated_fields:
            logger.info(
                "[openai_chat][compat] normalized extra_params for chat.completions: "
                f"base_url={base_url} model={model} changes={','.join(mutated_fields)}"
            )

        return normalized

    @staticmethod
    def _normalize_deepseek_reasoning_effort(value: Any) -> Optional[str]:
        raw = str(value or "").strip().lower()
        if not raw:
            return None
        if raw in {"max", "xhigh"}:
            return "max"
        if raw in {"high", "medium", "low"}:
            return "high"
        return None

    @classmethod
    def _normalize_deepseek_official_extra_params_in_place(
        cls,
        normalized: Dict[str, Any],
        *,
        mutated_fields: List[str],
    ) -> None:
        """DeepSeek 官方 chat wire 参数兼容。

        主干：上层继续表达通用 `thinking` / `reasoning` 语义。
        分支兼容：DeepSeek 官方 OpenAI 格式当前要求 `thinking` 只承载开关，
        推理强度使用顶层 `reasoning_effort`；是否开启 thinking 完全由模型组
        `REASONING_MODE` / `EXTRA_BODY` 决定，不因 tool 链路自动降级。
        """
        reasoning = normalized.pop("reasoning", None)
        effort = None
        if isinstance(reasoning, dict):
            effort = cls._normalize_deepseek_reasoning_effort(reasoning.get("effort"))
            mutated_fields.append("reasoning.effort->reasoning_effort@deepseek_official")
        elif reasoning is not None:
            mutated_fields.append("drop:reasoning@deepseek_official_invalid_shape")

        thinking = normalized.get("thinking")
        if isinstance(thinking, dict):
            thinking = dict(thinking)
            nested_effort = cls._normalize_deepseek_reasoning_effort(thinking.pop("reasoning_effort", None))
            if nested_effort:
                effort = nested_effort
                mutated_fields.append("thinking.reasoning_effort->reasoning_effort@deepseek_official")
            thinking_type = str(thinking.get("type") or "").strip().lower()
            if thinking_type == "disabled":
                for key in ("reasoning_effort", "model_reasoning_effort"):
                    if key in normalized:
                        normalized.pop(key, None)
                        mutated_fields.append(f"drop:{key}@deepseek_thinking_disabled")
                normalized["thinking"] = {"type": "disabled"}
                return
            if thinking_type == "enabled":
                normalized["thinking"] = {"type": "enabled"}
            elif thinking_type:
                normalized.pop("thinking", None)
                mutated_fields.append("drop:thinking@deepseek_official_invalid_type")
        elif thinking is not None:
            normalized.pop("thinking", None)
            mutated_fields.append("drop:thinking@deepseek_official_invalid_shape")

        top_effort = normalized.pop("model_reasoning_effort", None)
        if top_effort is not None:
            effort = cls._normalize_deepseek_reasoning_effort(top_effort)
            mutated_fields.append("model_reasoning_effort->reasoning_effort@deepseek_official")
        raw_reasoning_effort = normalized.get("reasoning_effort")
        if raw_reasoning_effort is not None:
            normalized_effort = cls._normalize_deepseek_reasoning_effort(raw_reasoning_effort)
            if normalized_effort:
                effort = normalized_effort
                if normalized_effort != raw_reasoning_effort:
                    mutated_fields.append("normalize:reasoning_effort@deepseek_official")
            else:
                normalized.pop("reasoning_effort", None)
                mutated_fields.append("drop:reasoning_effort@deepseek_official_invalid_value")

        if effort:
            normalized["reasoning_effort"] = effort
            if "thinking" not in normalized:
                normalized["thinking"] = {"type": "enabled"}
                mutated_fields.append("thinking.enabled@deepseek_official_reasoning_effort")

    @classmethod
    def _apply_internal_message_fields_to_payload(
        cls,
        payload: Dict[str, Any],
        *,
        base_url: str,
        model: str,
    ) -> None:
        messages = payload.get("messages")
        if not isinstance(messages, list):
            return

        replay_reasoning_content = bool(payload.pop(CHAT_REPLAY_REASONING_CONTENT_KEY, False))
        replayed = 0
        stripped = 0
        for message in messages:
            if not isinstance(message, dict):
                continue
            reasoning_content = message.pop(CHAT_INTERNAL_REASONING_CONTENT_KEY, None)
            if not isinstance(reasoning_content, str) or not reasoning_content.strip():
                continue
            if replay_reasoning_content and str(message.get("role") or "") == "assistant":
                message["reasoning_content"] = reasoning_content
                replayed += 1
            else:
                stripped += 1

        if replayed or stripped:
            logger.info(
                "[openai_chat][compat] applied internal reasoning_content fields: "
                f"base_url={base_url} model={model} enabled={replay_reasoning_content} "
                f"replayed={replayed} stripped={stripped}"
            )

    @classmethod
    def _payload_has_tool_conversation(cls, payload: Dict[str, Any]) -> bool:
        messages = payload.get("messages")
        if not isinstance(messages, list):
            return False
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "tool" or message.get("tool_calls"):
                return True
        return False

    @classmethod
    def _normalize_deepseek_official_messages_in_place(
        cls,
        payload: Dict[str, Any],
        *,
        base_url: str,
        model: str,
    ) -> None:
        if not cls._is_deepseek_official_chat_target(base_url=base_url):
            return

        messages = payload.get("messages")
        if not isinstance(messages, list):
            return

        changed = 0
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue

            text_parts: List[str] = []
            for seg in content:
                if not isinstance(seg, dict):
                    continue
                seg_type = str(seg.get("type") or "").strip().lower()
                if seg_type in {"", "text", "input_text", "output_text"}:
                    text = seg.get("text")
                    if text is None:
                        text = seg.get("content")
                    if isinstance(text, str) and text:
                        text_parts.append(text)
                    continue
                text_parts.append(f"[{seg_type or '非文本内容'}已降级]")

            message["content"] = "".join(text_parts)
            changed += 1

        if changed:
            logger.info(
                "[openai_chat][compat][deepseek_official] normalized message content to strings: "
                f"base_url={base_url} model={model} changed={changed}"
            )

    @classmethod
    def _apply_deepseek_official_cache_compat_to_payload(
        cls,
        payload: Dict[str, Any],
        *,
        request: GenerationRequest,
        base_url: str,
    ) -> None:
        """DeepSeek 官方 chat 的缓存兼容。

        主干：
        - HCZ 继续用 request.context_id + cache_domain 维护自己的缓存命名空间。

        分支兼容：
        - DeepSeek 官方缓存自动开启，不吃 UI/模型组的显式 cache transport 字段。
        - 这里仅把 HCZ 既有缓存命名空间映射为 provider 侧 `user_id` 隔离键，
          并在流式请求中补 `stream_options.include_usage=true` 以拿到 usage。
        """
        if not cls._is_deepseek_official_chat_target(base_url=base_url):
            return

        stripped_fields: List[str] = []
        for key in DEEPSEEK_OFFICIAL_CACHE_TRANSPORT_FIELD_KEYS:
            if key in payload:
                payload.pop(key, None)
                stripped_fields.append(key)

        stream_include_usage_enabled = False
        if bool(payload.get("stream")):
            stream_options = payload.get("stream_options")
            if not isinstance(stream_options, dict):
                stream_options = {}
            if not bool(stream_options.get("include_usage")):
                stream_options["include_usage"] = True
                stream_include_usage_enabled = True
            if stream_options:
                payload["stream_options"] = stream_options

        existing_user_id = str(payload.get("user_id") or "").strip()
        normalized_context_id = str(request.context_id or "").strip() or "global"
        normalized_cache_domain = str((request.cache_hints or {}).get("cache_domain") or "").strip()
        if existing_user_id:
            user_id = existing_user_id
            user_id_source = "existing"
        else:
            user_id = cls._build_deepseek_official_cache_partition_user_id(request, base_url=base_url)
            payload["user_id"] = user_id
            user_id_source = "hcz_cache_namespace"

        if stripped_fields or stream_include_usage_enabled or user_id_source != "existing":
            logger.info(
                "[openai_chat][cache][deepseek_official] applied provider cache isolation compat: "
                f"base_url={base_url} model={request.model} context_id={request.context_id or ''} "
                f"cache_domain={normalized_cache_domain or '-'} namespace={normalized_context_id} "
                f"user_id_source={user_id_source} user_id={user_id} "
                f"stripped_fields={stripped_fields or ['<none>']} "
                f"stream_include_usage={stream_include_usage_enabled}"
            )


    def _turn_to_message(self, turn: MessageTurn, *, request: Optional[GenerationRequest] = None) -> Dict[str, Any]:
        """MessageTurn → chat.completions message dict"""
        msg: Dict[str, Any] = {"role": turn.role}

        if turn.name and turn.role != "tool":
            msg["name"] = turn.name

        reasoning_content = get_text_reasoning_content(getattr(turn, "reasoning_content", None))
        if turn.role == "assistant" and reasoning_content:
            msg[CHAT_INTERNAL_REASONING_CONTENT_KEY] = reasoning_content

        if turn.role == "tool" and turn.tool_call_id:
            msg["tool_call_id"] = turn.tool_call_id

        # tool_calls on assistant messages
        if turn.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in turn.tool_calls
            ]
            # assistant with tool_calls may also have text content
            content = self._parts_to_content(turn.parts, degrade_media=True)
            if content:
                msg["content"] = content
            else:
                msg["content"] = None
            return msg

        # Regular content
        content = self._parts_to_content(turn.parts, degrade_media=True)
        msg["content"] = content if content else ""
        return msg

    def _parts_to_content(
        self,
        parts: List[MessagePart],
        *,
        degrade_media: bool = True,
    ) -> Any:
        """MessagePart 列表 → content 字段

        如果只有纯文本，返回 str；如果有图片等，返回 list 格式。
        """
        if not parts:
            return ""

        # 检查是否需要 multimodal content array
        has_media = any(p.type != "text" for p in parts)

        if not has_media:
            return "".join(p.text or "" for p in parts)

        # Multimodal: build content array
        content_array: List[Dict[str, Any]] = []
        for part in parts:
            if part.type == "text":
                if part.text:
                    content_array.append({"type": "text", "text": part.text})
            elif part.type == "image":
                image_url = self._resolve_image_url(part)
                if image_url:
                    content_array.append({
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": part.detail},
                    })
            elif degrade_media:
                # audio/video/file → degrade to text
                degraded = self._degrade_media_part(part)
                if degraded.text:
                    content_array.append({"type": "text", "text": degraded.text})

        return content_array if content_array else ""

    @staticmethod
    def _resolve_image_url(part: MessagePart) -> Optional[str]:
        """将 MessagePart 的图片数据解析为 URL 或 data URI"""
        if part.data:
            mime = "image/jpeg" if str(part.mime_type or "").lower() == "image/jpg" else part.mime_type or "image/png"
            b64 = base64.b64encode(part.data).decode("ascii")
            return f"data:{mime};base64,{b64}"
        if part.url:
            if part.url.startswith("/") and Path(part.url).exists():
                path = Path(part.url)
                mime = mimetypes.guess_type(str(path))[0] or "image/png"
                if str(mime).lower() == "image/jpg":
                    mime = "image/jpeg"
                b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                return f"data:{mime};base64,{b64}"
            return part.url
        return None

    @staticmethod
    def _spec_to_function(spec: ToolSpec) -> Dict[str, Any]:
        """ToolSpec → OpenAI function tool"""
        return {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }

    # ── wire format → IR ──

    def _parse_response(self, data: Dict[str, Any], *, dump_id: Optional[str] = None) -> GenerationResult:
        """chat.completions 响应 → GenerationResult"""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        text = message.get("content")
        reasoning_content = message.get("reasoning_content")
        if not isinstance(reasoning_content, str) or not reasoning_content.strip():
            reasoning_content = None
        finish_reason = choice.get("finish_reason", "stop") or "stop"

        # 解析标准 tool_calls
        standard_calls: List[ToolCall] = []
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {"raw": args_str}
            standard_calls.append(ToolCall(
                id=tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                name=func.get("name", ""),
                arguments=args if isinstance(args, dict) else {},
            ))

        text_reasoning_content = None
        if isinstance(text, str) and text:
            text, text_reasoning_content = extract_text_reasoning_content(text)
        reasoning_content = merge_reasoning_content(reasoning_content, text_reasoning_content)

        # Qwen 兼容：从可见文本中提取
        text_calls: List[ToolCall] = []
        if text:
            text_calls, text = parse_qwen_tool_calls(text)

        tool_calls = merge_tool_calls(
            standard_calls if standard_calls else None,
            text_calls,
        )

        return GenerationResult(
            text=text if text and text.strip() else None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=data.get("usage"),
            raw_response=data,
            reasoning_content=reasoning_content,
            dump_id=dump_id,
        )

    def _parse_stream_chunk(
        self,
        data: Dict[str, Any],
        accumulated_text: str,
        accumulated_tool_calls: Dict[int, Dict[str, Any]],
    ) -> Optional[GenerationResult]:
        """解析单个 SSE chunk，返回增量结果或 None"""
        choices = data.get("choices", [])
        if not choices:
            usage = data.get("usage")
            if isinstance(usage, dict):
                return GenerationResult(
                    finish_reason="",
                    usage=usage,
                    raw_response=data,
                )
            return None

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason")

        # 文本增量
        text_delta = delta.get("content")

        # tool_calls 增量
        for tc in delta.get("tool_calls", []):
            idx = tc.get("index", 0)
            if idx not in accumulated_tool_calls:
                accumulated_tool_calls[idx] = {
                    "id": tc.get("id", ""),
                    "name": "",
                    "arguments": "",
                }
            if tc.get("id"):
                accumulated_tool_calls[idx]["id"] = tc["id"]
            func = tc.get("function", {})
            if func.get("name"):
                accumulated_tool_calls[idx]["name"] = func["name"]
            if func.get("arguments"):
                accumulated_tool_calls[idx]["arguments"] += func["arguments"]

        if finish_reason:
            # 最终结果
            tool_calls: List[ToolCall] = []
            for _, tc_data in sorted(accumulated_tool_calls.items()):
                args_str = tc_data["arguments"]
                try:
                    args = json.loads(args_str) if args_str else {}
                except json.JSONDecodeError:
                    args = {"raw": args_str}
                tool_calls.append(ToolCall(
                    id=tc_data["id"] or f"call_{uuid.uuid4().hex[:8]}",
                    name=tc_data["name"],
                    arguments=args if isinstance(args, dict) else {},
                ))

            final_text = accumulated_text
            text_reasoning_content = None
            if final_text:
                final_text, text_reasoning_content = extract_text_reasoning_content(final_text)
            # Qwen 文本 tool_call 兼容
            text_calls: List[ToolCall] = []
            if final_text:
                text_calls, final_text = parse_qwen_tool_calls(final_text)

            all_calls = merge_tool_calls(
                tool_calls if tool_calls else None,
                text_calls,
            )

            return GenerationResult(
                text=final_text if final_text and final_text.strip() else None,
                tool_calls=all_calls,
                finish_reason=finish_reason,
                usage=data.get("usage"),
                reasoning_content=merge_reasoning_content(None, text_reasoning_content),
            )

        return GenerationResult(
            text=text_delta,
            finish_reason="",  # 标记为增量
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
        """非流式 chat.completions 调用"""
        payload = self._build_payload(request)
        payload["stream"] = False
        payload.update(self._normalize_extra_params_for_chat(
            request.extra_params,
            base_url=base_url,
            model=request.model,
            has_tools=bool(request.tools),
        ))
        self._apply_internal_message_fields_to_payload(payload, base_url=base_url, model=request.model)
        self._apply_cache_hints_to_payload(payload, request=request, base_url=base_url)
        self._normalize_deepseek_official_messages_in_place(payload, base_url=base_url, model=request.model)
        self._apply_deepseek_official_cache_compat_to_payload(payload, request=request, base_url=base_url)

        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        async with httpx.AsyncClient(
            proxy=proxy, timeout=timeout, verify=False, trust_env=False
        ) as client:
            _, dump_id = dump_prompt_request(protocol="chat", payload=payload)
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            dump_prompt_response(protocol="chat", dump_id=dump_id, payload=data)

        return self._parse_response(data, dump_id=dump_id)

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
        """流式 chat.completions 调用"""
        payload = self._build_payload(request)
        payload["stream"] = True
        payload.update(self._normalize_extra_params_for_chat(
            request.extra_params,
            base_url=base_url,
            model=request.model,
            has_tools=bool(request.tools),
        ))
        self._apply_internal_message_fields_to_payload(payload, base_url=base_url, model=request.model)
        self._apply_cache_hints_to_payload(payload, request=request, base_url=base_url)
        self._normalize_deepseek_official_messages_in_place(payload, base_url=base_url, model=request.model)
        self._apply_deepseek_official_cache_compat_to_payload(payload, request=request, base_url=base_url)

        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        accumulated_text = ""
        accumulated_tool_calls: Dict[int, Dict[str, Any]] = {}

        async with httpx.AsyncClient(
            proxy=proxy, timeout=timeout, verify=False, trust_env=False
        ) as client:
            _, dump_id = dump_prompt_request(protocol="chat", payload=payload)
            async with client.stream(
                "POST", url, json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    dump_prompt_response(protocol="chat", dump_id=dump_id, payload=chunk_data, suffix="stream")

                    result = self._parse_stream_chunk(
                        chunk_data, accumulated_text, accumulated_tool_calls
                    )
                    if result:
                        if result.text and result.finish_reason == "":
                            accumulated_text += result.text
                        yield result
