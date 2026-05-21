"""模型组 → 协议发射器路由

根据 ModelConfigGroup 的配置决定使用哪个发射器：
- WIRE_API 显式指定时优先使用对应 emitter
- WIRE_API=default 时回退到现有自动判定逻辑
- CACHE_TRANSPORT_PROFILE 仍只表达传输/缓存偏好，不再承担显式协议开关职责

主干说明：
- 图片数量上限与图片物料化(base64 / inline bytes)在这里统一处理，避免按协议各修一份。
- 各协议 emitter 只负责序列化差异；媒体限额、优先级与老图降级顺序由路由层统一决策。
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import mimetypes
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from PIL import Image, ImageOps

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.uniapi_hosts import UNIAPI_HOSTS, is_uniapi_base_url
from holo_cortex_zero.schemas.ir import GenerationRequest, GenerationResult, MessagePart, MessageTurn, ToolCall

from .base import BaseEmitter, EmitterMediaCapabilities
from .gemini import GeminiEmitter
from .openai_chat import OpenAIChatEmitter
from .responses import ResponsesEmitter


MEDIA_POLICY_INTERNAL_PREFIX = "__hcz_"
MEDIA_POLICY_IMAGE_MAX_COUNT_KEY = "__hcz_image_max_count"
MEDIA_POLICY_IMAGE_INLINE_MAX_BYTES = 25_000_000
MEDIA_POLICY_TOOL_VIDEO_MAX_INLINE_BYTES = 8_000_000
MEDIA_POLICY_TOOL_VIDEO_MAX_DURATION_SECONDS = 60
MEDIA_POLICY_TOOL_VIDEO_MAX_COUNT = 1
MODEL_GROUP_WIRE_API_DEFAULT = "default"
MODEL_GROUP_WIRE_API_CHOICES = {"default", "chat", "responses", "gemini"}
UNI_GROK_COMPAT_HOSTS = set(UNIAPI_HOSTS)


def _normalize_model_group_wire_api(raw_value: Any) -> str:
    normalized = str(raw_value or "").strip().lower()
    if not normalized:
        return MODEL_GROUP_WIRE_API_DEFAULT
    if normalized == "chat.completions":
        normalized = "chat"
    if normalized == "response":
        normalized = "responses"
    if normalized not in MODEL_GROUP_WIRE_API_CHOICES:
        logger.warning(f"模型组 WIRE_API 非法，已回退 default: value={raw_value}")
        return MODEL_GROUP_WIRE_API_DEFAULT
    return normalized


def _parse_model_group_extra_body(raw_extra: Any) -> Dict[str, Any]:
    if raw_extra is None:
        return {}
    if isinstance(raw_extra, dict):
        return dict(raw_extra)
    if isinstance(raw_extra, str):
        text = raw_extra.strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except Exception:
            return {}
        if isinstance(payload, dict):
            return payload
    return {}


def _parse_target_host(base_url: str) -> str:
    raw = str(base_url or "").strip()
    if not raw:
        return ""
    try:
        parsed = httpx.URL(raw)
    except Exception:
        return ""
    return str(parsed.host or "").strip().lower()


def _is_uni_grok_target(*, base_url: str, model: str) -> bool:
    return _parse_target_host(base_url) in UNI_GROK_COMPAT_HOSTS and str(model or "").strip().lower().startswith("grok-")


def detect_model_group_protocol(group: Any, *, allow_legacy_wire_api: bool = False) -> str:
    """统一模型组协议判定。

    主干顺序：
    1) 新增模型组字段 `WIRE_API` 显式指定时，强制走对应协议。
    2) 若允许 legacy 兼容，则读取 EXTRA_BODY 里的 `wire_api` 旧写法。
    3) 否则保持当前自动判定逻辑不变。
    """

    profile = str(getattr(group, "CACHE_TRANSPORT_PROFILE", "none") or "none").strip().lower()
    model = str(getattr(group, "CHAT_MODEL", "") or "").strip().lower()
    base_url = str(getattr(group, "BASE_URL", "") or "").strip().lower()

    explicit_wire_api = _normalize_model_group_wire_api(getattr(group, "WIRE_API", MODEL_GROUP_WIRE_API_DEFAULT))
    if explicit_wire_api != MODEL_GROUP_WIRE_API_DEFAULT:
        return explicit_wire_api

    if allow_legacy_wire_api:
        extra_params = _parse_model_group_extra_body(getattr(group, "EXTRA_BODY", None))
        legacy_wire_api = _normalize_model_group_wire_api(extra_params.get("wire_api"))
        if legacy_wire_api != MODEL_GROUP_WIRE_API_DEFAULT:
            return legacy_wire_api

    if "gemini" in profile:
        return "gemini"
    if "generativelanguage.googleapis.com" in base_url:
        return "gemini"
    if base_url.rstrip("/").endswith("/gemini") or "/gemini/" in base_url:
        return "gemini"
    if base_url.rstrip("/").endswith("/v1beta") or "/v1beta/" in base_url:
        return "gemini"
    if "gemini" in model and is_uniapi_base_url(base_url):
        return "gemini"

    if "responses" in profile:
        return "responses"
    if profile not in ("none", ""):
        return "chat"

    if ResponsesEmitter._responses_compat_reason(base_url=base_url, model=model):
        return "responses"
    if ResponsesEmitter._is_any_gpt_responses_target(base_url=base_url, model=model):
        return "responses"
    return "responses"


@dataclass(frozen=True)
class _UserImageRef:
    turn_index: int
    part_index: int
    protected: bool = False

    @property
    def key(self) -> tuple[int, int]:
        return (self.turn_index, self.part_index)


@dataclass(frozen=True)
class _UserMediaRef:
    turn_index: int
    part_index: int
    part_type: str

    @property
    def key(self) -> tuple[int, int]:
        return (self.turn_index, self.part_index)


@dataclass(frozen=True)
class _RouterCacheUnit:
    unit_type: str
    digest: str
    turn_index: int
    part_index: int = -1
    cacheable: bool = False
    char_count: int = 0


@dataclass(frozen=True)
class _RouterCacheSnapshot:
    units: tuple[_RouterCacheUnit, ...]


@dataclass(frozen=True)
class _RouterCachePrepared:
    key: str
    units: tuple[_RouterCacheUnit, ...]


class LLMRouter:
    """根据模型组配置选择协议发射器并执行调用"""

    REASONING_REPLAY_TOOL_CALL_PLACEHOLDER = "。"

    def __init__(self) -> None:
        self._chat_emitter = OpenAIChatEmitter()
        self._responses_emitter = ResponsesEmitter()
        self._gemini_emitter = GeminiEmitter()
        self._cache_prefix_snapshots: dict[str, _RouterCacheSnapshot] = {}

    def _select_emitter(self, protocol: str) -> BaseEmitter:
        """根据协议类型选择发射器"""
        if protocol == "responses":
            return self._responses_emitter
        if protocol == "gemini":
            return self._gemini_emitter
        return self._chat_emitter

    @staticmethod
    def _merge_extra_params(
        group_extra_params: Optional[Dict[str, Any]],
        request_extra_params: Optional[Dict[str, Any]],
        *,
        stage: str,
        group_key: Optional[str],
    ) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        config_keys: list[str] = []
        request_keys: list[str] = []

        if isinstance(group_extra_params, dict) and group_extra_params:
            merged.update(group_extra_params)
            config_keys = sorted(group_extra_params.keys())
        if isinstance(request_extra_params, dict) and request_extra_params:
            merged.update(request_extra_params)
            request_keys = sorted(request_extra_params.keys())

        if config_keys:
            logger.info(
                "LLM extra params merged: "
                f"stage={stage}, group={group_key or ''}, config_keys={config_keys}, "
                f"request_keys={request_keys}, final_keys={sorted(merged.keys())}"
            )

        return merged

    @classmethod
    def _resolve_effective_protocol(
        cls,
        request: GenerationRequest,
        *,
        protocol: str,
        base_url: str,
    ) -> str:
        requested_protocol = str(protocol or "chat").strip().lower() or "chat"

        # 主干：协议仍由模型组 / 调用方决定。
        # 分支兼容：uni-grok 在 chat.completions 下工具调用不稳定，
        # 因此仅在“带 tools 的请求”上切回 responses 主链，避免复制并行工具主干。
        if requested_protocol == "chat" and _is_uni_grok_target(base_url=base_url, model=request.model) and request.tools:
            logger.info(
                "[uni_grok][router] switch protocol chat -> responses for tool-bearing request: "
                f"ctx={request.context_id or ''} model={request.model} base_url={base_url} tools={len(request.tools)}"
            )
            return "responses"

        return requested_protocol

    @staticmethod
    def _normalize_image_bytes_for_compat_target(
        *,
        base_url: str,
        model: str,
        mime_type: str,
        data: bytes,
        source: str,
    ) -> tuple[str, bytes, bool]:
        mime = str(mime_type or "image/png").strip().lower() or "image/png"
        if not data or mime != "image/gif":
            return mime_type, data, False
        if not _is_uni_grok_target(base_url=base_url, model=model):
            return mime_type, data, False

        try:
            with Image.open(io.BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image)
                normalized = image.convert("RGBA")
                output = io.BytesIO()
                normalized.save(output, format="PNG")
            converted = output.getvalue()
            logger.info(
                "[llm][image][compat] normalized GIF -> PNG for uni-grok target: "
                f"source={source} model={model} base_url={base_url} bytes={len(data)} -> {len(converted)}"
            )
            return "image/png", converted, True
        except Exception as exc:
            logger.warning(
                "[llm][image][compat] GIF normalization failed, keep original: "
                f"source={source} model={model} base_url={base_url} err={exc}"
            )
            return mime_type, data, False

    @classmethod
    def _normalize_user_images_for_compat_target_in_place(
        cls,
        messages: list[MessageTurn],
        *,
        context_id: str,
        protocol: str,
        base_url: str,
        model: str,
    ) -> int:
        converted = 0
        for turn_index, turn in enumerate(messages):
            if turn.role != "user":
                continue
            for part_index, part in enumerate(turn.parts):
                if part.type != "image" or part.data is None:
                    continue
                source = f"turn={turn_index}:part={part_index}:{cls._image_name_from_part(part)}"
                normalized_mime, normalized_data, changed = cls._normalize_image_bytes_for_compat_target(
                    base_url=base_url,
                    model=model,
                    mime_type=str(part.mime_type or "image/png"),
                    data=part.data,
                    source=source,
                )
                if not changed:
                    continue
                turn.parts[part_index] = MessagePart(
                    type="image",
                    data=normalized_data,
                    mime_type=normalized_mime,
                    detail=part.detail,
                    meta=cls._part_meta(part),
                )
                converted += 1

        if converted > 0:
            logger.info(
                "LLM image compatibility normalization applied: "
                f"ctx={context_id} protocol={protocol} model={model} base_url={base_url} converted={converted}"
            )

        return converted

    @staticmethod
    def _clone_part(part: MessagePart) -> MessagePart:
        data = bytes(part.data) if part.data is not None else None
        return MessagePart(
            type=part.type,
            text=part.text,
            url=part.url,
            data=data,
            mime_type=part.mime_type,
            detail=part.detail,
            meta=dict(part.meta or {}),
        )

    @classmethod
    def _clone_turn(cls, turn: MessageTurn) -> MessageTurn:
        tool_calls = None
        if turn.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tool_call.id,
                    name=tool_call.name,
                    arguments=dict(tool_call.arguments),
                    meta=dict(getattr(tool_call, "meta", {}) or {}),
                )
                for tool_call in turn.tool_calls
            ]
        return MessageTurn(
            role=turn.role,
            parts=[cls._clone_part(part) for part in turn.parts],
            name=turn.name,
            tool_call_id=turn.tool_call_id,
            tool_calls=tool_calls,
            reasoning_content=turn.reasoning_content,
        )

    @classmethod
    def _clone_request(
        cls,
        request: GenerationRequest,
        *,
        messages: Optional[list[MessageTurn]] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> GenerationRequest:
        return GenerationRequest(
            context_id=request.context_id,
            model=request.model,
            messages=messages if messages is not None else [cls._clone_turn(turn) for turn in request.messages],
            tools=list(request.tools),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream,
            extra_params=dict(extra_params) if extra_params is not None else dict(request.extra_params),
            cache_hints=dict(request.cache_hints),
        )

    @staticmethod
    def _extract_internal_image_max_count(extra_params: Dict[str, Any]) -> Optional[int]:
        raw = extra_params.get(MEDIA_POLICY_IMAGE_MAX_COUNT_KEY)
        if raw is None or raw == "":
            return None
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            logger.warning(f"LLM media policy ignore invalid image max count: {raw}")
            return None
        return max(parsed, 0)

    @staticmethod
    def _strip_internal_extra_params(extra_params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value
            for key, value in extra_params.items()
            if not str(key or "").startswith(MEDIA_POLICY_INTERNAL_PREFIX)
        }

    @classmethod
    def _ensure_reasoning_replay_for_tool_calls(cls, request: GenerationRequest) -> GenerationRequest:
        """保证开启思维链回填时，function call 历史段内 assistant 具备非空回填内容。

        主干：REPLAY_REASONING_CONTENT 表达的是内部 IR 的回填语义；只要模型组开启该语义，
        function call 历史段内的 assistant 就必须携带可回放的 reasoning_content。
        兜底：历史缺失真实思维链时写入最小占位，已有真实思维链绝不覆盖。
        """
        extra_params = request.extra_params if isinstance(request.extra_params, dict) else {}
        if not extra_params.get("replay_reasoning_content"):
            return request

        function_call_history_active = False
        needs_backfill = False
        for turn in request.messages:
            if turn.role == "tool":
                function_call_history_active = True
                continue
            if turn.role != "assistant":
                continue
            in_function_call_history = function_call_history_active or bool(turn.tool_calls)
            if not in_function_call_history:
                continue
            function_call_history_active = True
            if not str(getattr(turn, "reasoning_content", None) or "").strip():
                needs_backfill = True
                break

        if not needs_backfill:
            return request

        prepared = cls._clone_request(request)
        backfilled = 0
        function_call_history_active = False
        for turn in prepared.messages:
            if turn.role == "tool":
                function_call_history_active = True
                continue
            if turn.role != "assistant":
                continue
            in_function_call_history = function_call_history_active or bool(turn.tool_calls)
            if not in_function_call_history:
                continue
            function_call_history_active = True
            if str(getattr(turn, "reasoning_content", None) or "").strip():
                continue
            turn.reasoning_content = cls.REASONING_REPLAY_TOOL_CALL_PLACEHOLDER
            backfilled += 1

        if backfilled:
            logger.info(
                "LLM reasoning replay IR backfilled function-call assistant history: "
                f"ctx={request.context_id or ''} model={request.model} backfilled={backfilled}"
            )
        return prepared

    @staticmethod
    def _should_persist_reasoning_content(request: GenerationRequest) -> bool:
        extra_params = request.extra_params if isinstance(request.extra_params, dict) else {}
        return bool(extra_params.get("replay_reasoning_content"))

    @classmethod
    def _filter_result_reasoning_content(
        cls,
        result: GenerationResult,
        *,
        request: GenerationRequest,
    ) -> GenerationResult:
        """按模型组回填开关过滤模型返回的隐藏思维。

        主干：`replay_reasoning_content` 是唯一允许隐藏思维进入历史回放闭环的开关。
        未开启时，即使供应商返回了 reasoning_content，也只参与本轮解析，不向记录层外泄。
        """
        if cls._should_persist_reasoning_content(request):
            return result
        if not result or not str(getattr(result, "reasoning_content", None) or "").strip():
            return result
        logger.info(
            "LLM reasoning content dropped before persistence: "
            f"ctx={request.context_id or ''} model={request.model} replay_reasoning_content=false"
        )
        result.reasoning_content = None
        return result

    @staticmethod
    def _is_persona_reference_turn(turn: MessageTurn) -> bool:
        if turn.role != "user":
            return False
        return any(
            part.type == "text" and "【系统形象参考图】" in str(part.text or "")
            for part in turn.parts
        )

    @classmethod
    def _collect_user_image_refs(cls, messages: list[MessageTurn]) -> list[_UserImageRef]:
        refs: list[_UserImageRef] = []
        for turn_index, turn in enumerate(messages):
            if turn.role != "user":
                continue
            protected = cls._is_persona_reference_turn(turn)
            for part_index, part in enumerate(turn.parts):
                if part.type == "image":
                    refs.append(_UserImageRef(turn_index=turn_index, part_index=part_index, protected=protected))
        return refs

    @staticmethod
    def _image_name_from_part(part: MessagePart) -> str:
        if part.url:
            raw = str(part.url).split("?", 1)[0]
            name = raw.rsplit("/", 1)[-1].strip()
            if name:
                return name
        if part.mime_type and "/" in str(part.mime_type):
            suffix = str(part.mime_type).split("/", 1)[-1].strip() or "img"
            return f"image.{suffix}"
        return "image"

    @staticmethod
    def _media_name_from_part(part: MessagePart, *, fallback: str) -> str:
        if part.url:
            raw = str(part.url).split("?", 1)[0]
            name = raw.rsplit("/", 1)[-1].strip()
            if name:
                return name
        if part.mime_type and "/" in str(part.mime_type):
            suffix = str(part.mime_type).split("/", 1)[-1].strip() or fallback
            return f"{fallback}.{suffix}"
        return fallback

    @classmethod
    def _collect_user_media_refs(
        cls,
        messages: list[MessageTurn],
        *,
        media_types: set[str],
    ) -> list[_UserMediaRef]:
        refs: list[_UserMediaRef] = []
        for turn_index, turn in enumerate(messages):
            if turn.role != "user":
                continue
            for part_index, part in enumerate(turn.parts):
                if part.type in media_types:
                    refs.append(_UserMediaRef(turn_index=turn_index, part_index=part_index, part_type=part.type))
        return refs

    @staticmethod
    def _part_meta(part: MessagePart) -> Dict[str, Any]:
        return dict(part.meta or {})

    @staticmethod
    def _hash_json(value: Any) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def _cache_part_digest(cls, part: MessagePart) -> str:
        meta = cls._part_meta(part)
        stable_meta = {
            key: value
            for key, value in meta.items()
            if key in {
                "source",
                "tool_video_preserved",
                "tool_video_preserved_mode",
                "tool_video_degraded",
                "tool_video_degraded_reason",
                "video_degraded",
                "video_degraded_reason",
            }
        }
        if part.type == "text":
            return cls._hash_json({"type": "text", "text": str(part.text or ""), "meta": stable_meta})
        if part.data is not None:
            return cls._hash_json({
                "type": part.type,
                "data_hash": cls._hash_bytes(bytes(part.data)),
                "mime_type": str(part.mime_type or ""),
                "detail": str(part.detail or ""),
                "meta": stable_meta,
            })
        return cls._hash_json({
            "type": part.type,
            "url": str(part.url or "").split("?", 1)[0],
            "mime_type": str(part.mime_type or ""),
            "detail": str(part.detail or ""),
            "meta": stable_meta,
        })

    @classmethod
    def _build_cache_units(cls, request: GenerationRequest) -> list[_RouterCacheUnit]:
        units: list[_RouterCacheUnit] = []
        for turn_index, turn in enumerate(request.messages):
            units.append(_RouterCacheUnit(
                unit_type="turn",
                digest=cls._hash_json({
                    "role": turn.role,
                    "name": turn.name,
                    "tool_call_id": turn.tool_call_id,
                    "reasoning_content": turn.reasoning_content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                            "meta": getattr(tool_call, "meta", {}) or {},
                        }
                        for tool_call in (turn.tool_calls or [])
                    ],
                }),
                turn_index=turn_index,
            ))
            for part_index, part in enumerate(turn.parts):
                text = str(part.text or "") if part.type == "text" else ""
                units.append(_RouterCacheUnit(
                    unit_type=f"part:{part.type}",
                    digest=cls._cache_part_digest(part),
                    turn_index=turn_index,
                    part_index=part_index,
                    cacheable=part.type == "text" and bool(text),
                    char_count=len(text),
                ))
        return units

    @classmethod
    def _cache_prefix_snapshot_key(
        cls,
        request: GenerationRequest,
        *,
        protocol: str,
        base_url: str,
    ) -> str:
        tools_digest = cls._hash_json([
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "permission_level": tool.permission_level,
            }
            for tool in request.tools
        ])
        # 主干：cache_domain 是上层路由/模式身份的协议无关隔离键。
        # 分支兼容：具体供应商 wire 字段仍由各 emitter 决定，这里只影响本地前缀快照域。
        cache_domain = str((request.cache_hints or {}).get("cache_domain") or "").strip()
        return "\x1f".join([
            str(request.context_id or "").strip(),
            cache_domain,
            str(protocol or "").strip().lower(),
            str(base_url or "").strip().lower(),
            str(request.model or "").strip(),
            cls._hash_json(request.extra_params or {}),
            tools_digest,
        ])

    @classmethod
    def _prefix_hash(cls, units: list[_RouterCacheUnit], end_index: int) -> str:
        if end_index < 0:
            return ""
        return hashlib.sha256(
            "|".join(unit.digest for unit in units[: end_index + 1]).encode("utf-8", errors="ignore")
        ).hexdigest()[:16]

    @staticmethod
    def _prefix_chars(units: list[_RouterCacheUnit], end_index: int) -> int:
        if end_index < 0:
            return 0
        return sum(max(0, int(unit.char_count or 0)) for unit in units[: end_index + 1])

    @staticmethod
    def _first_prefix_break_reason(
        current_units: list[_RouterCacheUnit],
        previous_units: tuple[_RouterCacheUnit, ...],
        lcp_count: int,
    ) -> str:
        if not previous_units:
            return "no_previous_snapshot"
        if lcp_count >= len(current_units) and lcp_count >= len(previous_units):
            return "fully_equal"
        if lcp_count >= len(current_units):
            return "current_ended"
        if lcp_count >= len(previous_units):
            return "previous_ended"
        current = current_units[lcp_count]
        previous = previous_units[lcp_count]
        if current.unit_type != previous.unit_type:
            return f"unit_type:{previous.unit_type}->{current.unit_type}"
        return f"unit_digest:{current.unit_type}"

    def _apply_canonical_cache_prefix_hints(
        self,
        request: GenerationRequest,
        *,
        protocol: str,
        base_url: str,
    ) -> tuple[GenerationRequest, Optional[_RouterCachePrepared]]:
        if not request.cache_hints or not request.context_id:
            return request, None

        units = self._build_cache_units(request)
        key = self._cache_prefix_snapshot_key(request, protocol=protocol, base_url=base_url)
        previous = self._cache_prefix_snapshots.get(key)
        previous_units = previous.units if previous is not None else tuple()

        lcp_count = 0
        for current_unit, previous_unit in zip(units, previous_units):
            if current_unit.unit_type != previous_unit.unit_type or current_unit.digest != previous_unit.digest:
                break
            lcp_count += 1

        anchor_index = -1
        for index in range(lcp_count - 1, -1, -1):
            if units[index].cacheable:
                anchor_index = index
                break
        anchor_cacheable_index = -1
        if anchor_index >= 0:
            anchor_cacheable_index = sum(1 for unit in units[: anchor_index + 1] if unit.cacheable) - 1

        cache_hints = dict(request.cache_hints)
        cache_hints.update({
            "stable_prefix": "canonical_lcp",
            "stable_prefix_snapshot": "hit" if previous is not None else "miss",
            "stable_prefix_units": str(lcp_count),
            "stable_prefix_anchor_unit": str(anchor_index),
            "stable_prefix_anchor_cacheable_index": str(anchor_cacheable_index),
            "stable_prefix_hash": self._prefix_hash(units, anchor_index),
            "stable_prefix_chars": str(self._prefix_chars(units, anchor_index)),
            "stable_prefix_break_reason": self._first_prefix_break_reason(units, previous_units, lcp_count),
        })
        logger.info(
            "LLM canonical cache prefix measured: "
            f"ctx={request.context_id} protocol={protocol} model={request.model} "
            f"cache_domain={str(cache_hints.get('cache_domain') or '')} "
            f"snapshot={cache_hints['stable_prefix_snapshot']} units={len(units)} "
            f"lcp_units={lcp_count} anchor_unit={anchor_index} "
            f"anchor_cacheable_index={anchor_cacheable_index} "
            f"prefix_hash={cache_hints['stable_prefix_hash'] or '-'} "
            f"prefix_chars={cache_hints['stable_prefix_chars']} "
            f"break={cache_hints['stable_prefix_break_reason']}"
        )

        return (
            GenerationRequest(
                context_id=request.context_id,
                model=request.model,
                messages=request.messages,
                tools=request.tools,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=request.stream,
                extra_params=dict(request.extra_params),
                cache_hints=cache_hints,
            ),
            _RouterCachePrepared(key=key, units=tuple(units)),
        )

    def _remember_canonical_cache_prefix(self, prepared: Optional[_RouterCachePrepared]) -> None:
        if prepared is None or not prepared.units:
            return
        self._cache_prefix_snapshots[prepared.key] = _RouterCacheSnapshot(units=prepared.units)
        while len(self._cache_prefix_snapshots) > 128:
            self._cache_prefix_snapshots.pop(next(iter(self._cache_prefix_snapshots)))

    @classmethod
    def _is_tool_media_part(cls, part: MessagePart) -> bool:
        return str(cls._part_meta(part).get("source") or "").strip() == "tool"

    @classmethod
    def _tool_media_limit_int(cls, part: MessagePart, key: str, default: int) -> int:
        raw = cls._part_meta(part).get(key, default)
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            return default
        return max(parsed, 1)

    @classmethod
    def _tool_video_max_inline_bytes(cls, part: MessagePart) -> int:
        return cls._tool_media_limit_int(part, "max_inline_bytes", MEDIA_POLICY_TOOL_VIDEO_MAX_INLINE_BYTES)

    @classmethod
    def _tool_video_max_duration_seconds(cls, part: MessagePart) -> int:
        return cls._tool_media_limit_int(part, "max_duration_seconds", MEDIA_POLICY_TOOL_VIDEO_MAX_DURATION_SECONDS)

    @staticmethod
    def _meta_flag_explicit_false(meta: Dict[str, Any], key: str) -> bool:
        raw = meta.get(key)
        if isinstance(raw, bool):
            return raw is False
        normalized = str(raw or "").strip().lower()
        return normalized in {"0", "false", "no", "off", "disable", "disabled"}

    @classmethod
    def _should_preserve_tool_video(cls, part: MessagePart) -> bool:
        meta = cls._part_meta(part)
        if not cls._is_tool_media_part(part):
            return False
        if cls._meta_flag_explicit_false(meta, "preserve_video"):
            return False
        return True

    @staticmethod
    def _can_ffprobe() -> bool:
        return bool(shutil.which("ffprobe"))

    @classmethod
    def _probe_media_duration_seconds(cls, path: Path) -> Optional[float]:
        if not cls._can_ffprobe() or not path.exists() or not path.is_file():
            return None
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=20, check=False)
        except Exception:
            return None
        if result.returncode != 0:
            return None
        output = (result.stdout or b"").decode("utf-8", errors="ignore").strip()
        if not output:
            return None
        try:
            return float(output)
        except ValueError:
            return None

    @classmethod
    def _build_tool_video_notice_part(cls, part: MessagePart, reason: str) -> MessagePart:
        file_name = cls._media_name_from_part(part, fallback="video")
        meta = cls._part_meta(part)
        ui_notice = str(meta.get("ui_notice") or "").strip()
        product_path = str(part.url or "").strip()
        notice = f"[Tool视频降级: {file_name}] {reason}"
        if product_path:
            notice = f"{notice} 产物路径：{product_path}"
        if ui_notice:
            notice = f"{ui_notice} {notice}".strip()
        meta.update({"tool_video_degraded": True, "tool_video_degraded_reason": reason})
        return MessagePart(type="text", text=notice, meta=meta)

    @classmethod
    def _build_video_notice_part(cls, part: MessagePart, reason: str) -> MessagePart:
        file_name = cls._media_name_from_part(part, fallback="video")
        meta = cls._part_meta(part)
        notice = f"[视频降级: {file_name}] {reason}"
        product_path = str(part.url or "").strip()
        if product_path:
            notice = f"{notice} 产物路径：{product_path}"
        meta.update({"video_degraded": True, "video_degraded_reason": reason})
        return MessagePart(type="text", text=notice, meta=meta)

    @staticmethod
    def _mark_tool_video_preserved_meta(meta: Dict[str, Any], mode: str) -> Dict[str, Any]:
        next_meta = dict(meta or {})
        next_meta.update({
            "tool_video_preserved": True,
            "tool_video_preserved_mode": str(mode or "prepared").strip() or "prepared",
        })
        return next_meta

    @classmethod
    def _prepare_tool_video_part_for_mainline(cls, part: MessagePart) -> Optional[MessagePart]:
        max_inline_bytes = cls._tool_video_max_inline_bytes(part)
        max_duration_seconds = cls._tool_video_max_duration_seconds(part)
        meta = cls._part_meta(part)

        if part.data is not None:
            if len(part.data) > max_inline_bytes:
                return None
            return MessagePart(
                type="video",
                data=bytes(part.data),
                mime_type=part.mime_type,
                detail=part.detail,
                meta=cls._mark_tool_video_preserved_meta(meta, "inline"),
            )

        url = str(part.url or "").strip()
        if not url or url.startswith(("http://", "https://", "data:")):
            return None

        path = Path(url)
        if not path.exists() or not path.is_file():
            return None

        duration = cls._probe_media_duration_seconds(path)
        if path.stat().st_size <= max_inline_bytes and (duration is None or duration <= max_duration_seconds):
            return MessagePart(
                type="video",
                url=str(path),
                mime_type=part.mime_type or mimetypes.guess_type(str(path))[0] or "video/mp4",
                detail=part.detail,
                meta=cls._mark_tool_video_preserved_meta(meta, "path"),
            )

        if not cls._can_ffmpeg():
            return None

        with tempfile.NamedTemporaryFile(prefix="hcz_tool_video_", suffix=".mp4", delete=False) as output_file:
            output_path = Path(output_file.name)
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-t",
            str(max(1, int(max_duration_seconds))),
            "-vf",
            "scale='min(960,iw)':-2:flags=lanczos",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "32",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=max(30, int(max_duration_seconds) + 20),
                check=False,
            )
            if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size <= 0:
                output_path.unlink(missing_ok=True)
                return None
            duration = cls._probe_media_duration_seconds(output_path)
            if output_path.stat().st_size > max_inline_bytes or (duration is not None and duration > max_duration_seconds):
                output_path.unlink(missing_ok=True)
                return None
            return MessagePart(
                type="video",
                url=str(output_path),
                mime_type="video/mp4",
                detail=part.detail,
                meta=cls._mark_tool_video_preserved_meta(meta, "compressed"),
            )
        except Exception:
            output_path.unlink(missing_ok=True)
            return None

    @classmethod
    def _apply_tool_video_policy_in_place(
        cls,
        messages: list[MessageTurn],
        *,
        emitter_capabilities: EmitterMediaCapabilities,
        protocol: str,
        context_id: str,
        model: str,
    ) -> tuple[int, int]:
        refs = cls._collect_user_media_refs(messages, media_types={"video"})
        preserve_candidates: list[_UserMediaRef] = []
        for ref in refs:
            part = messages[ref.turn_index].parts[ref.part_index]
            if cls._should_preserve_tool_video(part):
                preserve_candidates.append(ref)

        keep_keys = {ref.key for ref in preserve_candidates[-MEDIA_POLICY_TOOL_VIDEO_MAX_COUNT:]}
        preserved = 0
        degraded = 0

        for ref in preserve_candidates:
            turn = messages[ref.turn_index]
            part = turn.parts[ref.part_index]
            if ref.key not in keep_keys:
                turn.parts[ref.part_index] = cls._build_tool_video_notice_part(part, "超过保留上限，仅保留最近 1 条视频。")
                degraded += 1
                continue
            if not emitter_capabilities.accepts_video_parts:
                turn.parts[ref.part_index] = cls._build_tool_video_notice_part(
                    part,
                    "当前发射器不接受 video part，已统一降级为文本说明。",
                )
                degraded += 1
                continue
            prepared = cls._prepare_tool_video_part_for_mainline(part)
            if prepared is None:
                max_mb = cls._tool_video_max_inline_bytes(part) / 1_000_000
                max_seconds = cls._tool_video_max_duration_seconds(part)
                turn.parts[ref.part_index] = cls._build_tool_video_notice_part(
                    part,
                    f"无法压缩到 {max_mb:.1f}MB / {max_seconds}s 限制内，已降级为文本说明。",
                )
                degraded += 1
                continue
            turn.parts[ref.part_index] = prepared
            preserved += 1

        if preserved or degraded:
            logger.info(
                "LLM media policy tool video summary: "
                f"ctx={context_id} protocol={protocol} emitter={emitter_capabilities.name} model={model} "
                f"accepts_video={emitter_capabilities.accepts_video_parts} preserved={preserved} degraded={degraded} "
                f"candidates={len(preserve_candidates)}"
            )
        return preserved, degraded

    @staticmethod
    def _remove_part_indexes(turn: MessageTurn, indexes: set[int]) -> None:
        if not indexes:
            return
        turn.parts = [part for idx, part in enumerate(turn.parts) if idx not in indexes]

    @staticmethod
    def _prune_empty_text_parts(messages: list[MessageTurn]) -> None:
        for turn in messages:
            turn.parts = [part for part in turn.parts if part.type != "text" or str(part.text or "").strip()]

    @staticmethod
    def _can_ffmpeg() -> bool:
        return bool(shutil.which("ffmpeg"))

    @classmethod
    def _extract_audio_preview_from_path(cls, path: Path, *, max_seconds: int) -> Optional[bytes]:
        if not cls._can_ffmpeg() or not path.exists() or not path.is_file():
            return None
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-t",
            str(max(1, int(max_seconds))),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            "pipe:1",
        ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=max(20, int(max_seconds) + 10), check=False)
        except Exception:
            return None
        output = result.stdout or b""
        if result.returncode != 0 or len(output) < 44:
            return None
        return output

    @classmethod
    def _rewrite_video_parts_for_multimodal(
        cls,
        messages: list[MessageTurn],
        *,
        emitter_capabilities: EmitterMediaCapabilities,
        protocol: str,
        context_id: str,
        model: str,
        max_seconds: int,
    ) -> tuple[int, int]:
        _, protected_degraded = cls._apply_tool_video_policy_in_place(
            messages,
            emitter_capabilities=emitter_capabilities,
            protocol=protocol,
            context_id=context_id,
            model=model,
        )

        rewritten = 0
        degraded = 0
        for ref in cls._collect_user_media_refs(messages, media_types={"video"}):
            turn = messages[ref.turn_index]
            part = turn.parts[ref.part_index]
            if cls._should_preserve_tool_video(part):
                continue
            file_name = cls._media_name_from_part(part, fallback="video")
            wav: Optional[bytes] = None
            path_hint = Path(part.url) if part.url and str(part.url).startswith("/") else None
            if path_hint is not None:
                wav = cls._extract_audio_preview_from_path(path_hint, max_seconds=max_seconds)

            if wav:
                turn.parts[ref.part_index] = MessagePart(
                    type="audio",
                    data=wav,
                    mime_type="audio/wav",
                    meta=cls._part_meta(part),
                )
                rewritten += 1
                continue

            turn.parts[ref.part_index] = cls._build_video_notice_part(
                part,
                "无法提取音频预览，已降级为文本说明。",
            )
            degraded += 1
            logger.warning(
                "LLM media policy video->audio rewrite failed, degrade to path text only: "
                f"ctx={context_id} protocol={protocol} model={model} file={file_name}"
            )

        if rewritten or degraded:
            logger.info(
                "LLM media policy mainline video rewrite summary: "
                f"ctx={context_id} protocol={protocol} emitter={emitter_capabilities.name} model={model} "
                f"accepts_audio={emitter_capabilities.accepts_audio_parts} rewritten={rewritten} degraded={degraded}"
            )
        return rewritten, degraded

    @classmethod
    def _apply_audio_limit_in_place(
        cls,
        messages: list[MessageTurn],
        *,
        emitter_capabilities: EmitterMediaCapabilities,
        audio_max_count: int,
        context_id: str,
        protocol: str,
        model: str,
    ) -> int:
        if audio_max_count <= 0:
            return 0

        refs = cls._collect_user_media_refs(messages, media_types={"audio"})
        if len(refs) <= audio_max_count:
            return 0

        keep_keys = {ref.key for ref in refs[-audio_max_count:]}
        removals: dict[int, set[int]] = {}
        removed_names: list[str] = []
        for ref in refs:
            if ref.key in keep_keys:
                continue
            part = messages[ref.turn_index].parts[ref.part_index]
            removed_names.append(cls._media_name_from_part(part, fallback="audio"))
            removals.setdefault(ref.turn_index, set()).add(ref.part_index)

        for turn_index, indexes in removals.items():
            cls._remove_part_indexes(messages[turn_index], indexes)

        logger.info(
            "LLM media policy audio limit applied: "
            f"ctx={context_id} protocol={protocol} emitter={emitter_capabilities.name} model={model} "
            f"accepts_audio={emitter_capabilities.accepts_audio_parts} total={len(refs)} limit={audio_max_count} "
            f"removed={len(removed_names)} oldest_first={removed_names[:8]}"
        )
        return len(removed_names)

    @classmethod
    def _apply_image_limit_in_place(
        cls,
        messages: list[MessageTurn],
        *,
        image_max_count: Optional[int],
        context_id: str,
        protocol: str,
        model: str,
    ) -> int:
        if image_max_count is None:
            return 0

        refs = cls._collect_user_image_refs(messages)
        if image_max_count == 0:
            degraded = 0
            degraded_names: list[str] = []
            protected_degraded = 0
            for ref in refs:
                turn = messages[ref.turn_index]
                part = turn.parts[ref.part_index]
                degraded_names.append(cls._image_name_from_part(part))
                if ref.protected:
                    protected_degraded += 1
                turn.parts[ref.part_index] = MessagePart(
                    type="text",
                    text=f"[图片禁用降级: {cls._image_name_from_part(part)}]",
                    meta=cls._part_meta(part),
                )
                degraded += 1

            if degraded > 0:
                logger.info(
                    "LLM media policy image zero limit applied: "
                    f"ctx={context_id} protocol={protocol} model={model} total={len(refs)} "
                    f"limit=0 protected_degraded={protected_degraded} degraded={degraded} "
                    f"oldest_first={degraded_names[:8]}"
                )
            return degraded

        if len(refs) <= image_max_count:
            return 0

        protected_refs = [ref for ref in refs if ref.protected]
        normal_refs = [ref for ref in refs if not ref.protected]
        keep_slots = max(image_max_count - len(protected_refs), 0)
        keep_normal_keys = {ref.key for ref in normal_refs[-keep_slots:]} if keep_slots > 0 else set()

        degraded = 0
        degraded_names: list[str] = []
        for ref in normal_refs:
            if ref.key in keep_normal_keys:
                continue
            turn = messages[ref.turn_index]
            part = turn.parts[ref.part_index]
            degraded_names.append(cls._image_name_from_part(part))
            turn.parts[ref.part_index] = MessagePart(
                type="text",
                text=f"[图片超限降级: {cls._image_name_from_part(part)}]",
                meta=cls._part_meta(part),
            )
            degraded += 1

        if degraded > 0:
            logger.info(
                "LLM media policy image limit applied: "
                f"ctx={context_id} protocol={protocol} model={model} total={len(refs)} "
                f"limit={image_max_count} protected={len(protected_refs)} degraded={degraded} "
                f"oldest_first={degraded_names[:8]}"
            )

        return degraded

    @staticmethod
    def _parse_data_uri(uri: str) -> tuple[str, bytes]:
        raw = str(uri or "").strip()
        if not raw.startswith("data:") or "," not in raw:
            raise ValueError("invalid data uri")
        header, payload = raw.split(",", 1)
        mime_type = header[5:].split(";", 1)[0].strip() or "application/octet-stream"
        try:
            if ";base64" in header.lower():
                return mime_type, base64.b64decode(payload, validate=True)
            return mime_type, payload.encode("utf-8")
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"invalid data uri payload: {exc}") from exc

    @staticmethod
    def _sniff_image_mime(data: bytes, *, fallback_name: str) -> str:
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if data.startswith(b"BM"):
            return "image/bmp"
        if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
            return "image/webp"
        guessed = mimetypes.guess_type(fallback_name)[0]
        return guessed or "application/octet-stream"

    @classmethod
    async def _read_image_part_bytes(
        cls,
        part: MessagePart,
        *,
        http_client: Optional[httpx.AsyncClient],
    ) -> tuple[str, bytes]:
        if part.data is not None:
            mime_type = part.mime_type or cls._sniff_image_mime(part.data, fallback_name=cls._image_name_from_part(part))
            if not str(mime_type).startswith("image/"):
                raise ValueError(f"unsupported inline image mime: {mime_type}")
            return mime_type, part.data

        url = str(part.url or "").strip()
        if not url:
            raise ValueError("empty image url")

        if url.startswith("data:"):
            mime_type, data = cls._parse_data_uri(url)
            sniffed = cls._sniff_image_mime(data, fallback_name="data-uri")
            mime_type = sniffed if str(sniffed).startswith("image/") else mime_type
            if len(data) > MEDIA_POLICY_IMAGE_INLINE_MAX_BYTES:
                raise ValueError(
                    f"inline image too large ({len(data)} > {MEDIA_POLICY_IMAGE_INLINE_MAX_BYTES})"
                )
            if not str(mime_type).startswith("image/"):
                raise ValueError(f"data uri is not image: {mime_type}")
            return mime_type, data

        if url.startswith(("http://", "https://")):
            if http_client is None:
                raise ValueError("http client unavailable for remote image")
            async with http_client.stream("GET", url) as response:
                response.raise_for_status()
                mime_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip()
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > MEDIA_POLICY_IMAGE_INLINE_MAX_BYTES:
                        raise ValueError(
                            f"remote image too large ({total} > {MEDIA_POLICY_IMAGE_INLINE_MAX_BYTES})"
                        )
            data = b"".join(chunks)
            name = Path(url.split("?", 1)[0]).name or "remote-image"
            sniffed = cls._sniff_image_mime(data, fallback_name=name)
            mime_type = sniffed if str(sniffed).startswith("image/") else mime_type
            if not str(mime_type).startswith("image/"):
                raise ValueError(f"remote content is not image: {mime_type}")
            return mime_type, data

        path = Path(url)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"image path not found: {url}")
        data = path.read_bytes()
        if len(data) > MEDIA_POLICY_IMAGE_INLINE_MAX_BYTES:
            raise ValueError(f"local image too large ({len(data)} > {MEDIA_POLICY_IMAGE_INLINE_MAX_BYTES})")
        mime_type = part.mime_type or cls._sniff_image_mime(data, fallback_name=path.name or "local-image")
        if not str(mime_type).startswith("image/"):
            raise ValueError(f"local content is not image: {mime_type}")
        return mime_type, data

    @classmethod
    async def _materialize_user_images_in_place(
        cls,
        messages: list[MessageTurn],
        *,
        context_id: str,
        protocol: str,
        model: str,
        proxy: Optional[str],
        timeout: float,
    ) -> tuple[int, int]:
        materialized = 0
        degraded = 0
        http_client: Optional[httpx.AsyncClient] = None
        try:
            for turn in messages:
                if turn.role != "user":
                    continue
                for index, part in enumerate(turn.parts):
                    if part.type != "image":
                        continue
                    if part.data is not None and part.url is None:
                        continue
                    url = str(part.url or "").strip()
                    try:
                        if url.startswith(("http://", "https://")) and http_client is None:
                            http_client = httpx.AsyncClient(
                                proxy=proxy,
                                timeout=timeout,
                                verify=False,
                                trust_env=False,
                                follow_redirects=True,
                            )
                        mime_type, data = await cls._read_image_part_bytes(part, http_client=http_client)
                        turn.parts[index] = MessagePart(
                            type="image",
                            data=data,
                            mime_type=mime_type,
                            detail=part.detail,
                            meta=cls._part_meta(part),
                        )
                        materialized += 1
                    except Exception as exc:
                        degraded += 1
                        file_name = cls._image_name_from_part(part)
                        turn.parts[index] = MessagePart(
                            type="text",
                            text=f"[图片读取失败降级: {file_name}]",
                            meta=cls._part_meta(part),
                        )
                        logger.warning(
                            "LLM media policy image materialize failed: "
                            f"ctx={context_id} protocol={protocol} model={model} file={file_name} err={exc}"
                        )
        finally:
            if http_client is not None:
                await http_client.aclose()

        if materialized or degraded:
            logger.info(
                "LLM media policy image base materialized: "
                f"ctx={context_id} protocol={protocol} model={model} materialized={materialized} degraded={degraded}"
            )
        return materialized, degraded

    async def _prepare_request(
        self,
        request: GenerationRequest,
        *,
        emitter_capabilities: EmitterMediaCapabilities,
        protocol: str,
        base_url: str,
        proxy: Optional[str],
        timeout: float,
    ) -> GenerationRequest:
        extra_params = dict(request.extra_params) if isinstance(request.extra_params, dict) else {}
        image_max_count = self._extract_internal_image_max_count(extra_params)
        sanitized_extra_params = self._strip_internal_extra_params(extra_params)
        has_user_images = any(
            turn.role == "user" and any(part.type == "image" for part in turn.parts)
            for turn in request.messages
        )
        has_user_media = any(
            turn.role == "user" and any(part.type in {"audio", "video"} for part in turn.parts)
            for turn in request.messages
        )
        extra_params_changed = sanitized_extra_params != extra_params

        if not has_user_images and not has_user_media and not extra_params_changed:
            return request

        prepared = self._clone_request(request, extra_params=sanitized_extra_params)

        if has_user_images:
            self._apply_image_limit_in_place(
                prepared.messages,
                image_max_count=image_max_count,
                context_id=request.context_id,
                protocol=protocol,
                model=request.model,
            )
            await self._materialize_user_images_in_place(
                prepared.messages,
                context_id=request.context_id,
                protocol=protocol,
                model=request.model,
                proxy=proxy,
                timeout=timeout,
            )
            self._normalize_user_images_for_compat_target_in_place(
                prepared.messages,
                context_id=request.context_id,
                protocol=protocol,
                base_url=base_url,
                model=request.model,
            )

        if has_user_media:
            self._rewrite_video_parts_for_multimodal(
                prepared.messages,
                emitter_capabilities=emitter_capabilities,
                protocol=protocol,
                context_id=request.context_id,
                model=request.model,
                max_seconds=int(getattr(config, "AI_REPLY_MULTIMODAL_MEDIA_MAX_SECONDS", 60) or 60),
            )
            self._apply_audio_limit_in_place(
                prepared.messages,
                emitter_capabilities=emitter_capabilities,
                audio_max_count=int(getattr(config, "AI_REPLY_MULTIMODAL_AUDIO_MAX_COUNT", 4) or 4),
                context_id=request.context_id,
                protocol=protocol,
                model=request.model,
            )
            self._prune_empty_text_parts(prepared.messages)

        if extra_params_changed:
            logger.info(
                "LLM media policy stripped internal extra params: "
                f"ctx={request.context_id} protocol={protocol} model={request.model} "
                f"internal_keys={[key for key in extra_params.keys() if str(key).startswith(MEDIA_POLICY_INTERNAL_PREFIX)]}"
            )

        return prepared

    async def generate(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        protocol: str = "chat",
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GenerationResult:
        effective_protocol = self._resolve_effective_protocol(
            request,
            protocol=protocol,
            base_url=base_url,
        )
        emitter = self._select_emitter(effective_protocol)
        emitter_capabilities = emitter.get_media_capabilities()
        logger.info(
            "LLM emitter capabilities selected: "
            f"ctx={request.context_id} protocol={effective_protocol} emitter={emitter_capabilities.name} "
            f"image={emitter_capabilities.accepts_image_parts} "
            f"audio={emitter_capabilities.accepts_audio_parts} "
            f"video={emitter_capabilities.accepts_video_parts} "
            f"native_tools={emitter_capabilities.native_tool_calling} notes={emitter_capabilities.notes}"
        )
        prepared_request = await self._prepare_request(
            request,
            emitter_capabilities=emitter_capabilities,
            protocol=effective_protocol,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout,
        )
        prepared_request = self._ensure_reasoning_replay_for_tool_calls(prepared_request)
        prepared_request, cache_prepared = self._apply_canonical_cache_prefix_hints(
            prepared_request,
            protocol=effective_protocol,
            base_url=base_url,
        )
        result = await emitter.generate(
            prepared_request,
            api_key=api_key,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout,
            extra_headers=extra_headers,
        )
        self._remember_canonical_cache_prefix(cache_prepared)
        return self._filter_result_reasoning_content(result, request=prepared_request)

    async def generate_stream(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        protocol: str = "chat",
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[GenerationResult, None]:
        effective_protocol = self._resolve_effective_protocol(
            request,
            protocol=protocol,
            base_url=base_url,
        )
        emitter = self._select_emitter(effective_protocol)
        emitter_capabilities = emitter.get_media_capabilities()
        logger.info(
            "LLM emitter capabilities selected: "
            f"ctx={request.context_id} protocol={effective_protocol} emitter={emitter_capabilities.name} "
            f"image={emitter_capabilities.accepts_image_parts} "
            f"audio={emitter_capabilities.accepts_audio_parts} "
            f"video={emitter_capabilities.accepts_video_parts} "
            f"native_tools={emitter_capabilities.native_tool_calling} notes={emitter_capabilities.notes}"
        )
        prepared_request = await self._prepare_request(
            request,
            emitter_capabilities=emitter_capabilities,
            protocol=effective_protocol,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout,
        )
        prepared_request = self._ensure_reasoning_replay_for_tool_calls(prepared_request)
        prepared_request, cache_prepared = self._apply_canonical_cache_prefix_hints(
            prepared_request,
            protocol=effective_protocol,
            base_url=base_url,
        )
        completed = False
        try:
            async for chunk in emitter.generate_stream(
                prepared_request,
                api_key=api_key,
                base_url=base_url,
                proxy=proxy,
                timeout=timeout,
                extra_headers=extra_headers,
            ):
                yield self._filter_result_reasoning_content(chunk, request=prepared_request)
            completed = True
        finally:
            if completed:
                self._remember_canonical_cache_prefix(cache_prepared)

    async def call_with_fallback(
        self,
        request: GenerationRequest,
        *,
        primary_api_key: str,
        primary_base_url: str,
        primary_protocol: str = "chat",
        primary_proxy: Optional[str] = None,
        primary_extra_params: Optional[Dict[str, Any]] = None,
        primary_group_key: Optional[str] = None,
        fallback_group_key: Optional[str] = None,
        fallback_model: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
        fallback_base_url: Optional[str] = None,
        fallback_protocol: Optional[str] = None,
        fallback_proxy: Optional[str] = None,
        fallback_extra_params: Optional[Dict[str, Any]] = None,
        timeout: float = 120.0,
    ) -> GenerationResult:
        """带 fallback 的调用：主模型组失败时切换到备用组"""
        request_extra_params = dict(request.extra_params) if isinstance(request.extra_params, dict) else {}
        non_stream_request = GenerationRequest(
            context_id=request.context_id,
            model=request.model,
            messages=request.messages,
            tools=request.tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
            extra_params=self._merge_extra_params(
                primary_extra_params,
                request_extra_params,
                stage="primary",
                group_key=primary_group_key,
            ),
            cache_hints=dict(request.cache_hints),
        )

        if request.cache_hints:
            logger.debug(
                "LLM router preserved cache hints for primary request: "
                f"protocol={primary_protocol}, model={request.model}, "
                f"cache_hints={dict(request.cache_hints)}"
            )

        try:
            result = await self.generate(
                non_stream_request,
                api_key=primary_api_key,
                base_url=primary_base_url,
                protocol=primary_protocol,
                proxy=primary_proxy,
                timeout=timeout,
            )
            if result and (result.text or result.tool_calls):
                return result
            logger.warning(
                f"主模型组返回空结果: group={primary_group_key or ''} model={request.model} "
                f"protocol={primary_protocol} base_url={primary_base_url}"
            )
        except Exception as e:
            try:
                logger.warning(
                    f"主模型组调用失败: group={primary_group_key or ''} model={request.model} "
                    f"protocol={primary_protocol} type={type(e).__name__} err={e!r}",
                    exc_info=True,
                )
            except Exception as log_error:
                logger.error(
                    "主模型组失败日志记录异常，但仍继续 fallback: group={} model={} protocol={} err_type={} log_type={} log_err={!r}",
                    primary_group_key or '',
                    request.model,
                    primary_protocol,
                    type(e).__name__,
                    type(log_error).__name__,
                    log_error,
                )

        if fallback_base_url and fallback_api_key:
            if not str(fallback_model or "").strip():
                logger.warning(
                    "Fallback 模型组缺少模型名，已跳过 fallback: "
                    f"primary_group={primary_group_key or ''}, fallback_group={fallback_group_key or ''}, "
                    f"primary_model={request.model}, fallback_base_url={fallback_base_url}"
                )
                raise LLMAPIChainExhaustedError("fallback 模型组缺少模型名")

            fallback_request = GenerationRequest(
                context_id=request.context_id,
                model=str(fallback_model or "").strip(),
                messages=request.messages,
                tools=request.tools,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
                extra_params=self._merge_extra_params(
                    fallback_extra_params,
                    request_extra_params,
                    stage="fallback",
                    group_key=fallback_group_key,
                ),
                cache_hints=dict(request.cache_hints),
            )
            try:
                logger.info(
                    "LLM fallback route: "
                    f"primary_group={primary_group_key or ''}, fallback_group={fallback_group_key or ''}, "
                    f"primary_model={request.model}, fallback_model={fallback_request.model}, "
                    f"primary_base_url={primary_base_url}, fallback_base_url={fallback_base_url}, "
                    f"primary_protocol={primary_protocol}, fallback_protocol={fallback_protocol or 'chat'}"
                )
                return await self.generate(
                    fallback_request,
                    api_key=fallback_api_key,
                    base_url=fallback_base_url,
                    protocol=fallback_protocol or "chat",
                    proxy=fallback_proxy,
                    timeout=timeout,
                )
            except Exception as e2:
                logger.error(
                    f"Fallback 模型组也失败: group={fallback_group_key or ''} model={fallback_request.model} "
                    f"protocol={fallback_protocol or 'chat'} type={type(e2).__name__} err={e2!r}",
                    exc_info=True,
                )

        raise LLMAPIChainExhaustedError("所有模型组均不可用")


class LLMAPIChainExhaustedError(Exception):
    """所有模型组链路都已耗尽"""
    pass


llm_router = LLMRouter()
