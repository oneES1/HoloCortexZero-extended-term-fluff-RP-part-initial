from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any, List, Optional, Tuple

import httpx
from httpx import Timeout

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.config import ModelConfigGroup
from holo_cortex_zero.core.proxy_utils import resolve_model_group_proxy
from holo_cortex_zero.services.agent.creator import ContentSegment, OpenAIChatMessage


def _extract_image_from_images_field(images: Any) -> Optional[str]:
    return _deep_find_image(images)


def _collect_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "").strip().lower() == "text":
            text = item.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _extract_image_ref_from_content(content: Any) -> Optional[str]:
    if content is None:
        return None

    if isinstance(content, str):
        text = content.strip()
        if not text:
            return None
        match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", text)
        if match:
            return match.group(1).strip()
        match = re.search(r'<img\s+src=["\']([^"\']+)["\']', text)
        if match:
            return match.group(1).strip()
        match = re.search(r"data:image/[^;]+;base64,[A-Za-z0-9+/=_\-\r\n]+", text)
        if match:
            return match.group(0).strip()
        match = re.search(r"(https?://\S+)", text)
        if match:
            return match.group(1).strip()
        return None

    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip().lower()
            if item_type == "image_url":
                image_url = item.get("image_url")
                if isinstance(image_url, dict):
                    value = str(image_url.get("url") or image_url.get("image_url") or "").strip()
                    if value:
                        return value
                    data = str(image_url.get("data") or image_url.get("b64_json") or "").strip()
                    if data:
                        return data if data.startswith("data:image/") else f"data:image/png;base64,{data}"
                elif isinstance(image_url, str) and image_url.strip():
                    return image_url.strip()
            else:
                image_url = item.get("image_url")
                if isinstance(image_url, dict):
                    value = str(image_url.get("url") or image_url.get("image_url") or "").strip()
                    if value:
                        return value
                value = str(item.get("url") or "").strip()
                if value.startswith(("http://", "https://", "data:image/")):
                    return value
                data = str(item.get("data") or item.get("b64_json") or item.get("base64") or "").strip()
                if data:
                    return data if data.startswith("data:image/") else f"data:image/png;base64,{data}"
    return None


def _sniff_image_mime(head: bytes) -> Optional[str]:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head.startswith(b"RIFF") and len(head) >= 12 and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def _try_parse_base64_image(raw: str) -> Optional[Tuple[str, str]]:
    if not raw:
        return None
    cleaned = re.sub(r"\s+", "", raw)
    if len(cleaned) < 1024:
        return None
    cleaned = cleaned.replace("-", "+").replace("_", "/")
    pad_len = (-len(cleaned)) % 4
    if pad_len:
        cleaned += "=" * pad_len
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", cleaned):
        return None
    try:
        head_len = min(len(cleaned), 4096)
        head_len -= head_len % 4
        head = base64.b64decode(cleaned[:head_len], validate=False)
    except Exception:
        return None
    mime_type = _sniff_image_mime(head)
    if not mime_type:
        return None
    return mime_type, cleaned


def _normalize_image_candidate(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("data:image/"):
        return text
    if text.startswith(("http://", "https://")):
        return text
    parsed = _try_parse_base64_image(text)
    if parsed:
        mime_type, cleaned = parsed
        return f"data:{mime_type};base64,{cleaned}"
    return None


def _deep_find_image(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        text = obj.strip()
        if not text:
            return None
        if text.startswith("data:image/") or text.startswith(("http://", "https://")):
            return text
        match = re.search(r"data:image/[^;]+;base64,[A-Za-z0-9+/=_\-\r\n]+", text)
        if match:
            return match.group(0).strip()
        parsed = _try_parse_base64_image(text)
        if parsed:
            mime_type, cleaned = parsed
            return f"data:{mime_type};base64,{cleaned}"
        return None
    if isinstance(obj, dict):
        for key in ("url", "image_url", "imageUrl", "imageURL", "data", "b64_json", "base64"):
            found = _deep_find_image(obj.get(key))
            if found:
                return found
        for value in obj.values():
            found = _deep_find_image(value)
            if found:
                return found
        return None
    if isinstance(obj, list):
        for value in obj:
            found = _deep_find_image(value)
            if found:
                return found
    return None


async def generate_image_via_chat(
    model_group: ModelConfigGroup,
    prompt: str,
    *,
    timeout: float = 300.0,
    system_prompt: Optional[str] = None,
    use_system_role: bool = False,
    reference_images: Optional[List[Tuple[str, str]]] = None,
    stream_mode: bool = False,
    image_detail: Optional[str] = None,
    retry_on_image_upload_err: int = 2,
) -> str:
    if system_prompt is None:
        system_prompt = (
            "You are an image-capable model. Generate exactly one final image that matches the user's request. "
            "Output the image only (no text, no captions, no markdown)."
        )

    user_message = OpenAIChatMessage.create_empty("user")
    if reference_images:
        for image_data, image_desc in reference_images:
            if not image_data:
                continue
            seg = ContentSegment.image_content(image_data)
            if image_detail:
                try:
                    if isinstance(seg.get("image_url"), dict) and "detail" not in seg["image_url"]:
                        seg["image_url"]["detail"] = image_detail
                except Exception:
                    pass
            user_message = user_message.add(seg)
            if image_desc:
                user_message = user_message.add(ContentSegment.text_content(f"{image_desc}\n"))

    if not use_system_role and system_prompt:
        user_message = user_message.add(ContentSegment.text_content(f"{system_prompt}\n\n{prompt}"))
    else:
        user_message = user_message.add(ContentSegment.text_content(prompt))

    messages = []
    if use_system_role and system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append(user_message.to_dict())

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {model_group.API_KEY}",
    }
    payload: dict[str, Any] = {
        "model": model_group.CHAT_MODEL,
        "messages": messages,
        "stream": stream_mode,
    }

    if getattr(model_group, "EXTRA_BODY", None):
        try:
            extra = json.loads(model_group.EXTRA_BODY) if model_group.EXTRA_BODY else None
        except Exception:
            extra = None
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key not in {"model", "messages", "stream"}:
                    payload[key] = value

    try:
        model_name = str(getattr(model_group, "CHAT_MODEL", "") or "")
        model_type = str(getattr(model_group, "MODEL_TYPE", "") or "")
        if "gemini" in model_name.lower() and model_type == "draw":
            generation_config = payload.get("generationConfig")
            if not isinstance(generation_config, dict):
                generation_config = {}
                payload["generationConfig"] = generation_config
            if "responseModalities" not in generation_config:
                generation_config["responseModalities"] = ["Text", "Image"]
            elif isinstance(generation_config.get("responseModalities"), list):
                modalities = generation_config["responseModalities"]
                if not any(str(item).strip().lower() == "image" for item in modalities):
                    generation_config["responseModalities"] = [*modalities, "Image"]
    except Exception:
        pass

    collected_text = ""
    collected_raw_content: Any = None
    collected_image_data: Optional[str] = None
    collected_image_ref: Optional[str] = None
    raw_response_json: Any = None
    proxy = resolve_model_group_proxy(
        model_group,
        group_key=str(getattr(model_group, "GROUP_NAME", "") or getattr(model_group, "CHAT_MODEL", "") or ""),
        source="tools.image_generation",
    )

    async with httpx.AsyncClient(timeout=Timeout(read=timeout, write=timeout, connect=10, pool=10), proxy=proxy, trust_env=False) as client:
        if stream_mode:
            async with client.stream(
                "POST",
                f"{model_group.BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    raw = line.strip()
                    if not raw or not raw.startswith("data:"):
                        continue
                    data_str = raw[5:].lstrip()
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk_data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    image_data = delta.get("image")
                    if image_data:
                        if isinstance(image_data, list) and image_data:
                            first = image_data[0]
                            if isinstance(first, dict):
                                collected_image_data = first.get("data") or first.get("b64_json") or ""
                            elif isinstance(first, str):
                                collected_image_data = first
                        elif isinstance(image_data, dict):
                            collected_image_data = (
                                image_data.get("data")
                                or image_data.get("b64_json")
                                or image_data.get("base64")
                                or image_data.get("image")
                                or ""
                            )
                        elif isinstance(image_data, str):
                            collected_image_data = image_data
                    if not collected_image_ref:
                        collected_image_ref = _extract_image_ref_from_content(delta.get("content"))
                    if not collected_image_ref:
                        collected_image_ref = _extract_image_from_images_field(delta.get("images"))
                    content_data = delta.get("content")
                    if content_data:
                        if isinstance(content_data, str):
                            collected_text += content_data
                        else:
                            collected_raw_content = content_data
                            collected_text += _collect_text_from_content(content_data)
        else:
            response = await client.post(
                f"{model_group.BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            raw_response_json = data
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("模型未返回任何内容")
            message = choices[0].get("message", {})
            image_data = message.get("image")
            if image_data:
                if isinstance(image_data, list) and image_data:
                    first = image_data[0]
                    if isinstance(first, dict):
                        collected_image_data = first.get("data") or first.get("b64_json") or ""
                    elif isinstance(first, str):
                        collected_image_data = first
                elif isinstance(image_data, dict):
                    collected_image_data = (
                        image_data.get("data")
                        or image_data.get("b64_json")
                        or image_data.get("base64")
                        or image_data.get("image")
                        or ""
                    )
                elif isinstance(image_data, str):
                    collected_image_data = image_data
            content_data = message.get("content")
            if content_data:
                if isinstance(content_data, str):
                    collected_text = content_data
                else:
                    collected_raw_content = content_data
                    collected_text += _collect_text_from_content(content_data)
            if not collected_image_ref:
                collected_image_ref = _extract_image_ref_from_content(message.get("content"))
            if not collected_image_ref:
                collected_image_ref = _extract_image_from_images_field(message.get("images"))

    if collected_image_ref:
        return collected_image_ref
    if collected_image_data:
        normalized = _normalize_image_candidate(collected_image_data)
        if normalized:
            return normalized

    extracted = _extract_image_ref_from_content(collected_raw_content) or _extract_image_ref_from_content(collected_text)
    if extracted:
        return extracted

    deep_found = _deep_find_image(raw_response_json) or _deep_find_image(collected_raw_content)
    if deep_found:
        return deep_found

    hint = (collected_text or "").strip()
    aux_hint = str(collected_image_data or "").strip()
    hint_for_retry = f"{hint}\n{aux_hint}".strip().lower()
    if retry_on_image_upload_err > 0 and ("image upload err" in hint_for_retry or "upload err" in hint_for_retry):
        logger.warning(f"检测到上游返回 image upload err，自动重试剩余 {retry_on_image_upload_err} 次")
        await asyncio.sleep(1.2)
        return await generate_image_via_chat(
            model_group,
            prompt,
            timeout=timeout,
            system_prompt=system_prompt,
            use_system_role=use_system_role,
            reference_images=reference_images,
            stream_mode=False,
            image_detail=image_detail,
            retry_on_image_upload_err=retry_on_image_upload_err - 1,
        )

    if hint or aux_hint:
        merged_hint = (hint or aux_hint)[:200]
        raise ValueError(f"未能从模型响应中提取图片（模型返回了文本但没有图片）：{merged_hint}")
    raise ValueError("未能从模型响应中提取图片，请检查模型是否支持图像生成或提示词是否合适")
