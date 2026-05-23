"""Reasoning content normalization helpers.

主干：IR 层仍只传 `reasoning_content: str`，但字符串内部统一为 HCZ envelope，
避免 chat / Responses / Gemini 协议专属字段在跨协议切换时互相污染。
分支兼容：读取旧数据时兼容 plain text、旧 Responses JSON、旧 Gemini JSON。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


ENVELOPE_PROTOCOL = "hcz_reasoning_envelope"
ENVELOPE_VERSION = 1
_THINK_TAG = re.compile(r"<\s*(/?)\s*think(?:\s+[^>]*)?\s*>", re.IGNORECASE)


def _normalize_reasoning_text(text: str) -> str:
    value = _THINK_TAG.sub("", str(text or "")).strip()
    return value


def extract_text_reasoning_content(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Extract hidden reasoning embedded in `<think>`-style text.

    返回 `(visible_text, reasoning_content)`。

    兜底范围：
    - `<think>hidden</think>visible`
    - `visible<think>hidden</think>visible`
    - `hidden</think>visible`
    - `hidden<think>visible`（部分网关只输出一个尾部 think 标签，且未必带 `/`）
    - `<think>hidden`（缺失尾标签）
    """
    raw = str(text or "")
    if not raw:
        return None, None
    if "think" not in raw.lower() or "<" not in raw:
        return raw, None

    matches = list(_THINK_TAG.finditer(raw))
    if not matches:
        return raw, None

    if len(matches) == 1:
        match = matches[0]
        prefix = raw[: match.start()]
        suffix = raw[match.end() :]
        is_close = bool(match.group(1))

        if prefix.strip():
            reasoning = _normalize_reasoning_text(prefix)
            visible = _THINK_TAG.sub("", suffix).strip()
            return visible or None, reasoning or None

        if is_close:
            visible = _THINK_TAG.sub("", suffix).strip()
            return visible or None, None

        reasoning = _normalize_reasoning_text(suffix)
        return None, reasoning or None

    visible_segments: list[str] = []
    reasoning_segments: list[str] = []
    cursor = 0
    in_reasoning = False
    reasoning_start = 0

    for match in matches:
        is_close = bool(match.group(1))
        if not in_reasoning:
            if is_close:
                reasoning_segments.append(raw[cursor : match.start()])
                cursor = match.end()
                continue
            visible_segments.append(raw[cursor : match.start()])
            reasoning_start = match.end()
            in_reasoning = True
            continue

        if is_close:
            reasoning_segments.append(raw[reasoning_start : match.start()])
            cursor = match.end()
            in_reasoning = False
            continue

        reasoning_segments.append(raw[reasoning_start : match.start()])
        reasoning_start = match.end()

    if in_reasoning:
        reasoning_segments.append(raw[reasoning_start:])
    else:
        visible_segments.append(raw[cursor:])

    visible = _THINK_TAG.sub("", "".join(visible_segments)).strip()
    reasoning = "\n\n".join(
        item for item in (_normalize_reasoning_text(seg) for seg in reasoning_segments) if item
    ).strip()
    return visible or None, reasoning or None


def _extract_text_from_responses_summary(items: List[Dict[str, Any]]) -> Optional[str]:
    chunks: List[str] = []
    for item in items:
        summary = item.get("summary")
        if isinstance(summary, list):
            for entry in summary:
                if isinstance(entry, dict):
                    text = entry.get("text") or entry.get("summary")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text.strip())
                elif isinstance(entry, str) and entry.strip():
                    chunks.append(entry.strip())
        elif isinstance(summary, str) and summary.strip():
            chunks.append(summary.strip())
    return "\n\n".join(chunks).strip() or None


def build_reasoning_content(
    *,
    text: Optional[str] = None,
    responses_items: Optional[List[Dict[str, Any]]] = None,
    gemini_thought_signatures: Optional[List[str]] = None,
    origin_protocol: str = "",
) -> Optional[str]:
    normalized_text = _normalize_reasoning_text(str(text or ""))
    clean_responses_items = [dict(item) for item in responses_items or [] if isinstance(item, dict)]
    clean_signatures = [str(item).strip() for item in gemini_thought_signatures or [] if str(item).strip()]
    payload: Dict[str, Any] = {
        "protocol": ENVELOPE_PROTOCOL,
        "version": ENVELOPE_VERSION,
    }
    if origin_protocol:
        payload["origin_protocol"] = str(origin_protocol)
    if normalized_text:
        payload["text"] = normalized_text
    if clean_responses_items:
        payload["responses_items"] = clean_responses_items
    if clean_signatures:
        payload["gemini_thought_signatures"] = clean_signatures
    if len(payload) <= 2 and not origin_protocol:
        return None
    if len(payload) <= 3 and origin_protocol:
        return None
    return json.dumps(payload, ensure_ascii=False)


def parse_reasoning_content(reasoning_content: Optional[str]) -> Dict[str, Any]:
    raw = str(reasoning_content or "").strip()
    empty = {
        "text": None,
        "responses_items": [],
        "gemini_thought_signatures": [],
        "origin_protocol": "",
        "is_envelope": False,
    }
    if not raw:
        return empty

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        empty["text"] = _normalize_reasoning_text(raw)
        return empty

    if not isinstance(parsed, dict):
        empty["text"] = _normalize_reasoning_text(raw)
        return empty

    if parsed.get("protocol") == ENVELOPE_PROTOCOL:
        responses_items = [
            dict(item)
            for item in parsed.get("responses_items", [])
            if isinstance(item, dict) and item.get("type") == "reasoning"
        ]
        signatures = [
            str(item).strip()
            for item in parsed.get("gemini_thought_signatures", [])
            if str(item).strip()
        ]
        text = parsed.get("text")
        if not isinstance(text, str) or not text.strip():
            text = _extract_text_from_responses_summary(responses_items)
        return {
            "text": _normalize_reasoning_text(text or "") or None,
            "responses_items": responses_items,
            "gemini_thought_signatures": signatures,
            "origin_protocol": str(parsed.get("origin_protocol") or ""),
            "is_envelope": True,
        }

    if parsed.get("protocol") == "responses":
        items = [
            dict(item)
            for item in parsed.get("items", [])
            if isinstance(item, dict) and item.get("type") == "reasoning"
        ]
        return {
            **empty,
            "responses_items": items,
            "text": _extract_text_from_responses_summary(items),
            "origin_protocol": "responses",
        }

    if parsed.get("protocol") == "gemini":
        signatures = [
            str(item).strip()
            for item in parsed.get("thought_signatures", [])
            if str(item).strip()
        ]
        return {
            **empty,
            "gemini_thought_signatures": signatures,
            "origin_protocol": "gemini",
        }

    if "reasoning_content" in parsed and isinstance(parsed.get("reasoning_content"), str):
        return {**empty, "text": _normalize_reasoning_text(parsed["reasoning_content"])}

    empty["text"] = None if raw.startswith("{") else _normalize_reasoning_text(raw)
    return empty


def get_text_reasoning_content(reasoning_content: Optional[str]) -> Optional[str]:
    value = parse_reasoning_content(reasoning_content).get("text")
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def get_responses_reasoning_items(reasoning_content: Optional[str]) -> List[Dict[str, Any]]:
    return [dict(item) for item in parse_reasoning_content(reasoning_content).get("responses_items", [])]


def get_gemini_thought_signatures(reasoning_content: Optional[str]) -> List[str]:
    return [str(item).strip() for item in parse_reasoning_content(reasoning_content).get("gemini_thought_signatures", []) if str(item).strip()]


def merge_reasoning_content(primary: Optional[str], fallback: Optional[str]) -> Optional[str]:
    """Merge native/text reasoning into HCZ envelope."""
    parsed = parse_reasoning_content(primary)
    text = parsed.get("text") if isinstance(parsed.get("text"), str) else ""
    fallback_text = _normalize_reasoning_text(str(fallback or ""))
    if fallback_text and fallback_text not in str(text or ""):
        text = f"{text}\n\n{fallback_text}".strip() if text else fallback_text
    return build_reasoning_content(
        text=text or None,
        responses_items=parsed.get("responses_items", []),
        gemini_thought_signatures=parsed.get("gemini_thought_signatures", []),
        origin_protocol=str(parsed.get("origin_protocol") or ""),
    )


def format_text_reasoning_for_history(reasoning_content: Optional[str], visible_text: str = "") -> str:
    """Render text reasoning for providers that accept `<think>` history."""
    reasoning = get_text_reasoning_content(reasoning_content)
    visible = str(visible_text or "").strip()
    if not reasoning:
        return visible
    think_block = f"<think>\n{reasoning}\n</think>"
    return f"{think_block}\n\n{visible}" if visible else think_block
