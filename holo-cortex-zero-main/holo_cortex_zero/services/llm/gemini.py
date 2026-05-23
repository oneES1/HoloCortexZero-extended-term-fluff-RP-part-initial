"""Gemini 原生协议发射器。

主干说明：
- Gemini 走独立 emitter，不复用 `/responses` 主链。
- 主干负责 Gemini native `generateContent` / `streamGenerateContent` 协议与 tool calling。
- 分支兼容只做网关字段差异兜底，例如 camelCase / snake_case、`/v1` → relay base 重写。

兼容目标：
- Google Generative Language API
- `cdn.12ai.org/v1beta`
- `code.newcli.com/gemini`
- `api.uniapi.io/gemini` / `hk.uniapi.io/gemini`
- `api.uniapi.io/v1` / `hk.uniapi.io/v1` 上的 Gemini relay 自动改写
"""
from __future__ import annotations

import base64
import json
import mimetypes
import shutil
import subprocess
import tempfile
import re
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional
from urllib.parse import urlparse

import httpx

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.uniapi_hosts import UNIAPI_HOSTS
from holo_cortex_zero.schemas.ir import GenerationRequest, GenerationResult, MessagePart, MessageTurn, ToolCall, ToolSpec

from .base import BaseEmitter, EmitterMediaCapabilities
from .model_group_params import MODEL_GROUP_CACHE_TRANSPORT_PROFILE_EXTRA_KEY
from .prompt_logging import dump_prompt_request, dump_prompt_response
from .reasoning_text import build_reasoning_content, extract_text_reasoning_content, get_gemini_thought_signatures


GEMINI_MAX_INLINE_BYTES = 25_000_000
GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_OFFICIAL_HOST = "generativelanguage.googleapis.com"
GEMINI_UNIAPI_HOSTS = set(UNIAPI_HOSTS)
GEMINI_SNAKE_CASE_HOSTS = set(UNIAPI_HOSTS)
_GEMINI_TOOL_DESC_DROP_LINE = re.compile(
    r"(?:调用示例|Example:|Examples:|Args:|Returns:|不要使用 Markdown 代码块|必须输出|直接裸输)",
    re.IGNORECASE,
)
_GEMINI_SCHEMA_DROP_KEYS = {"$schema", "additionalProperties"}


class GeminiEmitter(BaseEmitter):
    """Gemini native `generateContent` 发射器。"""

    def get_media_capabilities(self) -> EmitterMediaCapabilities:
        return EmitterMediaCapabilities(
            name="gemini",
            accepts_image_parts=True,
            accepts_audio_parts=True,
            accepts_video_parts=True,
            native_tool_calling=True,
            notes="Gemini native 分支可原生接收 image/audio/video；tool 续链仍统一走文本结果。",
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

    @classmethod
    def _prefers_snake_case(cls, *, base_url: str) -> bool:
        host, _ = cls._parse_base_url(base_url)
        if host in GEMINI_SNAKE_CASE_HOSTS:
            return True
        return "uniapi" in str(base_url or "").strip().lower()

    @classmethod
    def _normalize_base_url(cls, *, base_url: str, model: str) -> str:
        raw = str(base_url or "").strip().rstrip("/")
        if not raw:
            return GEMINI_DEFAULT_BASE_URL

        host, path = cls._parse_base_url(raw)
        lowered = raw.lower()

        if GEMINI_OFFICIAL_HOST in host:
            return raw if "/v1" in lowered else f"{raw}/v1beta"

        if host in GEMINI_UNIAPI_HOSTS:
            if path == "/v1":
                return f"{raw[:-3]}/gemini/v1beta"
            if path == "/gemini":
                return f"{raw}/v1beta"

        if lowered.endswith("/gemini") or "/gemini/" in lowered:
            return raw if "/v1" in lowered else f"{raw}/v1beta"

        if lowered.endswith("/v1beta") or "/v1beta/" in lowered:
            return raw

        if "gemini" in str(model or "").strip().lower() and lowered.endswith("/v1"):
            return f"{raw[:-3]}/v1beta"

        return raw if "/v1" in lowered else f"{raw}/v1beta"

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        value = str(model or "").strip()
        if not value:
            return value
        if "/" in value:
            value = value.rsplit("/", 1)[-1].strip()
        if value.lower().startswith("models/"):
            value = value.split("/", 1)[-1].strip()
        return value

    @staticmethod
    def _build_headers(*, api_key: str, base_url: str, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        key = str(api_key or "").strip()
        lowered = str(base_url or "").strip().lower()
        if key:
            headers["x-goog-api-key"] = key
            if GEMINI_OFFICIAL_HOST not in lowered and not key.startswith("AIza"):
                headers["Authorization"] = f"Bearer {key}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    @staticmethod
    def _guess_mime_from_name(name: str, default: str = "application/octet-stream") -> str:
        guess, _ = mimetypes.guess_type(str(name or ""))
        return guess or default

    @staticmethod
    def _parse_data_uri(uri: str) -> tuple[str, bytes]:
        raw = str(uri or "").strip()
        if not raw.startswith("data:") or ";base64," not in raw:
            raise ValueError("not a base64 data uri")
        header, payload = raw.split(",", 1)
        mime_type = header[5:].split(";", 1)[0].strip() or "application/octet-stream"
        return mime_type, base64.b64decode(payload.encode("utf-8"), validate=False)

    @staticmethod
    def _sniff_mime_from_bytes(data: bytes, *, fallback_name: str) -> str:
        if not data:
            return "application/octet-stream"
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
            return "audio/wav"
        if data.startswith(b"OggS"):
            return "audio/ogg"
        if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
            return "audio/mpeg"
        if len(data) >= 12 and data[4:8] == b"ftyp":
            brand = data[8:12]
            if brand in {b"M4A ", b"M4B ", b"isom", b"mp41", b"mp42", b"iso2"}:
                ext = Path(fallback_name).suffix.lower()
                if ext in {".m4a", ".aac"}:
                    return "audio/mp4"
                return "video/mp4"
            if brand in {b"qt  "}:
                return "video/quicktime"
        if data.startswith(b"\x1A\x45\xDF\xA3"):
            ext = Path(fallback_name).suffix.lower()
            if ext in {".weba", ".ogg", ".oga", ".opus"}:
                return "audio/webm"
            return "video/webm"
        return GeminiEmitter._guess_mime_from_name(fallback_name)

    @staticmethod
    def _coerce_audio_mime(mime_type: str) -> str:
        lowered = str(mime_type or "").strip().lower()
        if lowered == "video/mp4":
            return "audio/mp4"
        if lowered == "video/webm":
            return "audio/webm"
        if lowered == "audio/x-wav":
            return "audio/wav"
        return mime_type

    @staticmethod
    def _normalize_uniapi_mime(mime_type: str) -> str:
        lowered = str(mime_type or "").strip().lower()
        if lowered == "audio/mpeg":
            return "audio/mp3"
        if lowered == "audio/x-wav":
            return "audio/wav"
        if lowered == "image/jpg":
            return "image/jpeg"
        if lowered == "video/quicktime":
            return "video/mov"
        return mime_type

    @staticmethod
    def _can_ffmpeg() -> bool:
        return bool(shutil.which("ffmpeg"))

    @classmethod
    def _ffmpeg_to_wav_from_path(cls, path: Path, *, seconds: int = 60) -> Optional[bytes]:
        if not cls._can_ffmpeg() or not path.exists():
            return None
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-t",
            str(max(1, int(seconds))),
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
            result = subprocess.run(command, capture_output=True, timeout=max(20, int(seconds) + 10), check=False)
        except Exception:
            return None
        output = result.stdout or b""
        if result.returncode != 0 or len(output) < 44:
            return None
        return output

    @classmethod
    def _maybe_transcode_audio(
        cls,
        *,
        mime_type: str,
        data: bytes,
        path_hint: Optional[Path],
        name_hint: str,
        max_seconds: int = 60,
    ) -> tuple[str, bytes]:
        lowered = str(mime_type or "").strip().lower()
        suffix = Path(name_hint).suffix.lower()
        needs_transcode = False
        if "silk" in lowered or "amr" in lowered:
            needs_transcode = True
        if suffix in {".silk", ".amr", ".pcm", ".caf"}:
            needs_transcode = True
        if not needs_transcode:
            return mime_type, data

        wav: Optional[bytes] = None
        if path_hint is not None:
            wav = cls._ffmpeg_to_wav_from_path(path_hint, seconds=max_seconds)
        if wav is None and cls._can_ffmpeg() and data:
            tmp_path: Optional[Path] = None
            try:
                with tempfile.NamedTemporaryFile(prefix="hcz_gemini_audio_", suffix=suffix or ".bin", delete=False) as file:
                    file.write(data)
                    tmp_path = Path(file.name)
                wav = cls._ffmpeg_to_wav_from_path(tmp_path, seconds=max_seconds)
            except Exception:
                wav = None
            finally:
                try:
                    if tmp_path is not None:
                        tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass

        if wav:
            logger.info(
                f"[gemini][media] transcoded unsupported audio to wav: mime={mime_type} name={name_hint} bytes={len(data)}->{len(wav)}"
            )
            return "audio/wav", wav
        return mime_type, data

    async def _read_part_bytes(
        self,
        http_client: httpx.AsyncClient,
        part: MessagePart,
        *,
        default_mime: str,
    ) -> tuple[str, bytes, str]:
        name_hint = "inline.bin"
        if part.data is not None:
            mime_type = part.mime_type or self._sniff_mime_from_bytes(part.data, fallback_name=name_hint)
            return mime_type, part.data, name_hint

        url = str(part.url or "").strip()
        if not url:
            raise ValueError("empty media url")

        if url.startswith("data:"):
            mime_type, data = self._parse_data_uri(url)
            if len(data) > GEMINI_MAX_INLINE_BYTES:
                raise ValueError(f"inline media too large ({len(data)} > {GEMINI_MAX_INLINE_BYTES})")
            return mime_type, data, "data-uri"

        if url.startswith(("http://", "https://")):
            response = await http_client.get(url)
            response.raise_for_status()
            data = response.content
            if len(data) > GEMINI_MAX_INLINE_BYTES:
                raise ValueError(f"remote media too large ({len(data)} > {GEMINI_MAX_INLINE_BYTES})")
            name_hint = Path(url.split("?", 1)[0]).name or name_hint
            mime_type = response.headers.get("content-type") or self._sniff_mime_from_bytes(data, fallback_name=name_hint)
            mime_type = str(mime_type).split(";", 1)[0].strip() or default_mime
            return mime_type, data, name_hint

        path = Path(url)
        if not path.exists():
            raise FileNotFoundError(f"media path not found: {url}")
        data = path.read_bytes()
        if len(data) > GEMINI_MAX_INLINE_BYTES:
            raise ValueError(f"local media too large ({len(data)} > {GEMINI_MAX_INLINE_BYTES})")
        name_hint = path.name
        mime_type = part.mime_type or self._sniff_mime_from_bytes(data, fallback_name=name_hint)
        return mime_type or default_mime, data, name_hint

    @staticmethod
    def _inline_part(
        *,
        inline_key: Literal["inline_data", "inlineData"],
        mime_key: Literal["mime_type", "mimeType"],
        mime_type: str,
        data: bytes,
    ) -> Dict[str, Any]:
        return {
            inline_key: {
                mime_key: mime_type,
                "data": base64.b64encode(data).decode("utf-8"),
            },
        }

    async def _message_parts_to_gemini_parts(
        self,
        parts: List[MessagePart],
        http_client: httpx.AsyncClient,
        *,
        role: str,
        inline_key: Literal["inline_data", "inlineData"],
        mime_key: Literal["mime_type", "mimeType"],
        mime_normalizer: Optional[Any] = None,
        include_text: bool = True,
    ) -> List[Dict[str, Any]]:
        gemini_parts: List[Dict[str, Any]] = []
        for part in parts:
            if part.type == "text":
                if include_text and part.text:
                    gemini_parts.append({"text": part.text})
                continue

            if role != "user":
                degraded = self._degrade_media_part(part)
                if degraded.text:
                    gemini_parts.append({"text": degraded.text})
                continue

            if part.type == "image":
                mime_type, data, _ = await self._read_part_bytes(http_client, part, default_mime="image/jpeg")
                normalized_mime = mime_normalizer(mime_type) if mime_normalizer else mime_type
                gemini_parts.append(
                    self._inline_part(
                        inline_key=inline_key,
                        mime_key=mime_key,
                        mime_type=str(normalized_mime or mime_type),
                        data=data,
                    ),
                )
                continue

            if part.type == "audio":
                mime_type, data, name_hint = await self._read_part_bytes(http_client, part, default_mime="audio/mpeg")
                mime_type = self._coerce_audio_mime(mime_type)
                path_hint = Path(part.url) if part.url and str(part.url).startswith("/") else None
                max_media_seconds = int(getattr(config, "AI_REPLY_MULTIMODAL_MEDIA_MAX_SECONDS", 60) or 60)
                mime_type, data = self._maybe_transcode_audio(
                    mime_type=mime_type,
                    data=data,
                    path_hint=path_hint,
                    name_hint=name_hint,
                    max_seconds=max_media_seconds,
                )
                normalized_mime = mime_normalizer(mime_type) if mime_normalizer else mime_type
                gemini_parts.append(
                    self._inline_part(
                        inline_key=inline_key,
                        mime_key=mime_key,
                        mime_type=str(normalized_mime or mime_type),
                        data=data,
                    ),
                )
                continue

            if part.type == "video":
                mime_type, data, _ = await self._read_part_bytes(http_client, part, default_mime="video/mp4")
                normalized_mime = mime_normalizer(mime_type) if mime_normalizer else mime_type
                gemini_parts.append(
                    self._inline_part(
                        inline_key=inline_key,
                        mime_key=mime_key,
                        mime_type=str(normalized_mime or mime_type),
                        data=data,
                    ),
                )
                continue

            degraded = self._degrade_media_part(part)
            if degraded.text:
                gemini_parts.append({"text": degraded.text})

        return gemini_parts

    @staticmethod
    def _tool_result_parts_to_text(parts: List[MessagePart]) -> str:
        text_parts = [part.text or "" for part in parts if part.type == "text" and part.text]
        payload = "".join(text_parts).strip()
        if payload:
            return payload

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

        preview_text = "\n".join([item for item in previews if item]).strip()
        return preview_text or "(空返回)"

    @classmethod
    def _tool_result_to_response(cls, parts: List[MessagePart]) -> Dict[str, Any]:
        return {"result": cls._tool_result_parts_to_text(parts)}

    @staticmethod
    def _sanitize_tool_description(description: str) -> str:
        raw = str(description or "").replace("\r\n", "\n").replace("\r", "\n")
        cleaned_lines: List[str] = []
        for line in raw.split("\n"):
            stripped = line.strip()
            if not stripped:
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
                continue
            if _GEMINI_TOOL_DESC_DROP_LINE.search(stripped):
                continue
            stripped = stripped.replace("**", "").replace("`", "")
            cleaned_lines.append(stripped)
        cleaned = "\n".join(cleaned_lines).strip()
        if not cleaned:
            cleaned = str(description or "").strip()
        if len(cleaned) > 1200:
            cleaned = cleaned[:1200].rstrip()
        return cleaned

    @staticmethod
    def _sanitize_tool_schema(schema: Any) -> Any:
        if isinstance(schema, dict):
            return {
                key: GeminiEmitter._sanitize_tool_schema(value)
                for key, value in schema.items()
                if key not in _GEMINI_SCHEMA_DROP_KEYS
            }
        if isinstance(schema, list):
            return [GeminiEmitter._sanitize_tool_schema(item) for item in schema]
        return schema

    @staticmethod
    def _spec_to_function_declaration(spec: ToolSpec) -> Dict[str, Any]:
        return {
            "name": spec.name,
            "description": GeminiEmitter._sanitize_tool_description(spec.description),
            "parameters": GeminiEmitter._sanitize_tool_schema(spec.parameters),
        }

    async def _turn_to_content(
        self,
        turn: MessageTurn,
        http_client: httpx.AsyncClient,
        *,
        inline_key: Literal["inline_data", "inlineData"],
        mime_key: Literal["mime_type", "mimeType"],
        include_role: bool,
        function_call_key: Literal["functionCall", "function_call"],
        function_response_key: Literal["functionResponse", "function_response"],
        tool_name_by_call_id: Dict[str, str],
        mime_normalizer: Optional[Any] = None,
        replay_reasoning_content: bool = False,
        thought_signature_key: Literal["thoughtSignature", "thought_signature"] = "thoughtSignature",
    ) -> Optional[Dict[str, Any]]:
        role = "model" if turn.role == "assistant" else "user"

        if turn.role == "tool":
            call_id = str(turn.tool_call_id or "").strip()
            tool_name = tool_name_by_call_id.get(call_id, "tool")
            tool_parts: List[Dict[str, Any]] = [{
                function_response_key: {
                    "name": tool_name,
                    "response": self._tool_result_to_response(turn.parts),
                },
            }]
            return {"role": "user", "parts": tool_parts} if include_role else {"parts": tool_parts}

        content_parts = await self._message_parts_to_gemini_parts(
            turn.parts,
            http_client,
            role="user" if turn.role == "user" else "assistant",
            inline_key=inline_key,
            mime_key=mime_key,
            mime_normalizer=mime_normalizer,
        )

        if turn.role == "assistant" and turn.tool_calls:
            replay_signatures = get_gemini_thought_signatures(turn.reasoning_content) if replay_reasoning_content else []
            for index, tool_call in enumerate(turn.tool_calls):
                call_part = {
                    function_call_key: {
                        "name": tool_call.name,
                        "args": tool_call.arguments,
                    },
                }
                # 主干：模型组 REPLAY_REASONING_CONTENT 决定是否回放隐藏思考。
                # 分支兼容：Gemini 用 thoughtSignature 续接思考，不使用 chat 的 reasoning_content 文本字段。
                if replay_reasoning_content:
                    signature = str((getattr(tool_call, "meta", {}) or {}).get("gemini_thought_signature") or "").strip()
                    if not signature and index < len(replay_signatures):
                        signature = replay_signatures[index]
                    if signature:
                        call_part[thought_signature_key] = signature
                content_parts.append(call_part)

        if not content_parts:
            return None
        return {"role": role, "parts": content_parts} if include_role else {"parts": content_parts}

    async def _build_payload(
        self,
        request: GenerationRequest,
        http_client: httpx.AsyncClient,
        *,
        base_url: str,
        style: Dict[str, Any],
    ) -> Dict[str, Any]:
        tool_name_by_call_id: Dict[str, str] = {}
        for turn in request.messages:
            for tool_call in turn.tool_calls or []:
                if tool_call.id and tool_call.name:
                    tool_name_by_call_id[str(tool_call.id)] = str(tool_call.name)

        system_text_parts: List[str] = []
        contents: List[Dict[str, Any]] = []
        mime_normalizer = self._normalize_uniapi_mime if "uniapi" in base_url.lower() else None

        replay_reasoning_content = bool(
            isinstance(request.extra_params, dict)
            and request.extra_params.get("replay_reasoning_content")
        )
        thought_signature_key: Literal["thoughtSignature", "thought_signature"] = (
            "thoughtSignature" if style["param_case"] == "camel" else "thought_signature"
        )

        for turn in request.messages:
            if turn.role == "system":
                for part in turn.parts:
                    if part.type == "text" and part.text:
                        system_text_parts.append(part.text)
                    elif part.type != "text":
                        degraded = self._degrade_media_part(part)
                        if degraded.text:
                            system_text_parts.append(degraded.text)
                continue

            content_item = await self._turn_to_content(
                turn,
                http_client,
                inline_key=style["inline_key"],
                mime_key=style["mime_key"],
                include_role=style["include_role"],
                function_call_key=style["function_call_key"],
                function_response_key=style["function_response_key"],
                tool_name_by_call_id=tool_name_by_call_id,
                mime_normalizer=mime_normalizer,
                replay_reasoning_content=replay_reasoning_content,
                thought_signature_key=thought_signature_key,
            )
            if content_item:
                contents.append(content_item)

        extra_params = dict(request.extra_params or {})
        generation_config = dict(extra_params.pop("generationConfig", {}) or {})
        generation_config.update(dict(extra_params.pop("generation_config", {}) or {}))

        if request.temperature is not None and "temperature" not in generation_config:
            generation_config["temperature"] = request.temperature

        top_p = extra_params.pop("top_p", extra_params.pop("topP", None))
        if top_p is not None and "topP" not in generation_config and "top_p" not in generation_config:
            generation_config["topP" if style["param_case"] == "camel" else "top_p"] = top_p

        top_k = extra_params.pop("top_k", extra_params.pop("topK", None))
        if top_k is not None and "topK" not in generation_config and "top_k" not in generation_config:
            generation_config["topK" if style["param_case"] == "camel" else "top_k"] = top_k

        max_output_tokens = request.max_tokens
        if max_output_tokens is None:
            max_output_tokens = extra_params.pop("max_output_tokens", extra_params.pop("maxOutputTokens", None))
        if max_output_tokens is not None and "maxOutputTokens" not in generation_config and "max_output_tokens" not in generation_config:
            generation_config[
                "maxOutputTokens" if style["param_case"] == "camel" else "max_output_tokens"
            ] = max_output_tokens

        stop_sequences = extra_params.pop("stop_sequences", extra_params.pop("stopSequences", None))
        if stop_sequences and "stopSequences" not in generation_config and "stop_sequences" not in generation_config:
            generation_config[
                "stopSequences" if style["param_case"] == "camel" else "stop_sequences"
            ] = stop_sequences

        incompatible_keys = {
            "reasoning",
            "thinking",
            "text",
            "store",
            "instructions",
            "response_format",
            "responses_legacy_role_rewrite",
            "disable_response_storage",
            "replay_reasoning_content",
            MODEL_GROUP_CACHE_TRANSPORT_PROFILE_EXTRA_KEY,
        }
        for key in list(extra_params.keys()):
            if key in incompatible_keys:
                extra_params.pop(key, None)

        payload: Dict[str, Any] = {"contents": contents}
        if system_text_parts:
            sys_text = "\n".join(system_text_parts)
            if style["system_parts_as_object"]:
                payload[style["system_key"]] = {"parts": {"text": sys_text}}
            else:
                payload[style["system_key"]] = {"parts": [{"text": sys_text}]}

        if generation_config:
            payload[style["generation_key"]] = generation_config

        if request.tools:
            declaration_key = style["function_declarations_key"]
            payload["tools"] = [{declaration_key: [self._spec_to_function_declaration(tool) for tool in request.tools]}]

        for key, value in extra_params.items():
            if key in {"contents", "tools", "generationConfig", "generation_config", "systemInstruction", "system_instruction"}:
                continue
            payload[key] = value

        return payload

    def _parse_response(self, data: Dict[str, Any], *, dump_id: Optional[str] = None) -> GenerationResult:
        if isinstance(data.get("error"), dict):
            error = data.get("error") or {}
            raise RuntimeError(f"gemini_failed[{error.get('code', 'unknown')}]: {error.get('message', 'request failed')}")

        candidates = data.get("candidates") or []
        candidate = candidates[0] if candidates else {}
        content = candidate.get("content") or {}
        parts = content.get("parts") or []

        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []
        thought_signatures: List[str] = []

        for part in parts:
            if not isinstance(part, dict):
                continue
            text = str(part.get("text") or "")
            if text and not bool(part.get("thought")):
                text_parts.append(text)

            thought_signature = part.get("thoughtSignature") or part.get("thought_signature")
            if isinstance(thought_signature, str) and thought_signature.strip():
                thought_signatures.append(thought_signature.strip())

            function_call = part.get("functionCall") or part.get("function_call")
            if isinstance(function_call, dict):
                name = str(function_call.get("name") or "").strip()
                args = function_call.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                if not isinstance(args, dict):
                    args = {"value": args}
                meta = {"gemini_thought_signature": thought_signature.strip()} if isinstance(thought_signature, str) and thought_signature.strip() else {}
                tool_calls.append(
                    ToolCall(
                        id=f"gemini_call_{uuid.uuid4().hex[:8]}",
                        name=name,
                        arguments=args,
                        meta=meta,
                    ),
                )

        usage = data.get("usageMetadata") or data.get("usage_metadata")
        finish_reason = str(candidate.get("finishReason") or candidate.get("finish_reason") or data.get("status") or "stop")
        text = "".join(text_parts).strip() or None
        text_reasoning_content = None
        if text:
            text, text_reasoning_content = extract_text_reasoning_content(text)
        reasoning_content = build_reasoning_content(
            text=text_reasoning_content,
            gemini_thought_signatures=thought_signatures,
            origin_protocol="gemini" if thought_signatures or text_reasoning_content else "",
        )
        return GenerationResult(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage if isinstance(usage, dict) else None,
            raw_response=data,
            reasoning_content=reasoning_content,
            dump_id=dump_id,
        )

    async def _post_with_style_retry(
        self,
        request: GenerationRequest,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        headers: Dict[str, str],
        stream_mode: bool,
    ) -> Dict[str, Any]:
        prefer_snake = self._prefers_snake_case(base_url=base_url)
        camel_with_role = {
            "inline_key": "inlineData",
            "mime_key": "mimeType",
            "system_key": "systemInstruction",
            "system_parts_as_object": False,
            "generation_key": "generationConfig",
            "function_declarations_key": "functionDeclarations",
            "function_call_key": "functionCall",
            "function_response_key": "functionResponse",
            "param_case": "camel",
            "include_role": True,
        }
        camel_no_role = dict(camel_with_role, include_role=False)
        snake_with_role = {
            "inline_key": "inline_data",
            "mime_key": "mime_type",
            "system_key": "system_instruction",
            "system_parts_as_object": True,
            "generation_key": "generation_config",
            "function_declarations_key": "function_declarations",
            "function_call_key": "function_call",
            "function_response_key": "function_response",
            "param_case": "snake",
            "include_role": True,
        }
        snake_no_role = dict(snake_with_role, include_role=False)
        mixed_with_role = dict(camel_with_role, inline_key="inline_data", mime_key="mime_type")
        mixed_no_role = dict(mixed_with_role, include_role=False)

        styles = (
            [snake_with_role, snake_no_role, mixed_with_role, mixed_no_role, camel_with_role, camel_no_role]
            if prefer_snake
            else [camel_with_role, camel_no_role, mixed_with_role, mixed_no_role, snake_with_role, snake_no_role]
        )

        model = self._normalize_model_name(request.model)
        endpoint = ":streamGenerateContent?alt=sse" if stream_mode else ":generateContent"
        url = f"{base_url.rstrip('/')}/models/{model}{endpoint}"
        last_400_body = ""

        for index, style in enumerate(styles, start=1):
            payload = await self._build_payload(request, http_client, base_url=base_url, style=style)
            logger.info(
                "[gemini] request prepared: "
                f"url={url} style={index}/{len(styles)} include_role={style['include_role']} "
                f"contents={len(payload.get('contents', []))} tools={len(request.tools)} stream={stream_mode}"
            )
            _, dump_id = dump_prompt_request(protocol="gemini", payload=payload, suffix=f"style{index:02d}")

            if stream_mode:
                async with http_client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code == 400:
                        last_400_body = (await response.aread()).decode("utf-8", errors="ignore")[:400]
                        logger.warning(f"[gemini][compat] 400 stream style#{index}: {last_400_body}")
                        continue
                    response.raise_for_status()
                    aggregated: Dict[str, Any] = {"candidates": [], "usageMetadata": {}}
                    events: List[Dict[str, Any]] = []
                    async for line in response.aiter_lines():
                        raw = str(line or "").strip()
                        if not raw:
                            continue
                        if raw.startswith("data:"):
                            raw = raw.split("data:", 1)[1].strip()
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(event, dict) and isinstance(event.get("error"), dict):
                            error = event.get("error") or {}
                            raise RuntimeError(
                                f"gemini_failed[{error.get('code', 'unknown')}]: {error.get('message', 'request failed')}"
                            )
                        events.append(event)
                    if not events:
                        raise RuntimeError("gemini_stream_empty_result")
                    final_event = events[-1]
                    if isinstance(final_event, dict):
                        dump_prompt_response(protocol="gemini", dump_id=dump_id, payload=final_event)
                        final_event["_hcz_dump_id"] = dump_id
                        return final_event
                    break

            response = await http_client.post(url, headers=headers, json=payload)
            if response.status_code == 400:
                last_400_body = response.text[:400]
                logger.warning(f"[gemini][compat] 400 style#{index}: {last_400_body}")
                continue
            response.raise_for_status()
            data = response.json()
            dump_prompt_response(protocol="gemini", dump_id=dump_id, payload=data)
            data["_hcz_dump_id"] = dump_id
            return data

        raise RuntimeError(f"gemini_compat_exhausted: {last_400_body}")

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
        gemini_base = self._normalize_base_url(base_url=base_url, model=request.model)
        headers = self._build_headers(api_key=api_key, base_url=gemini_base, extra_headers=extra_headers)
        async with httpx.AsyncClient(proxy=proxy, timeout=timeout, verify=False, trust_env=False) as client:
            data = await self._post_with_style_retry(
                request,
                http_client=client,
                base_url=gemini_base,
                headers=headers,
                stream_mode=False,
            )
        result = self._parse_response(data, dump_id=str(data.get("_hcz_dump_id") or "") or None)
        logger.info(
            "[gemini] request finished: "
            f"model={self._normalize_model_name(request.model)} base={gemini_base} "
            f"text={'yes' if result.text else 'no'} tools={len(result.tool_calls)} finish={result.finish_reason}"
        )
        return result

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
        result = await self.generate(
            request,
            api_key=api_key,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout,
            extra_headers=extra_headers,
        )
        yield result
