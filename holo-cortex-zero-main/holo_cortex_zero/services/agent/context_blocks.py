from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _default_section_kind(block_type: str) -> str:
    normalized = str(block_type or "").strip().lower()
    if normalized.startswith("current_turn"):
        return "current_turn"
    if normalized.startswith("window"):
        return "window"
    if normalized.startswith("persona"):
        return "persona"
    if normalized.startswith("short_memory"):
        return "short_memory"
    if normalized.startswith("stage2"):
        return "stage2"
    if normalized.startswith("immutable"):
        return "immutable"
    return normalized or "block"


def build_context_block(
    *,
    block_id: str,
    block_type: str,
    order_key: int,
    source_scope: str,
    text_payload: str = "",
    image_digest_refs: Optional[List[str]] = None,
    image_identity_refs: Optional[List[str]] = None,
    paired_text_ref: str = "",
    mutable: bool = True,
    section_kind: str = "",
    message_anchor: str = "",
    physical_order: Optional[int] = None,
) -> Dict[str, Any]:
    resolved_text_payload = str(text_payload or "")
    resolved_image_digest_refs = [str(item) for item in (image_digest_refs or []) if str(item or "")]
    resolved_image_identity_refs = [str(item) for item in (image_identity_refs or []) if str(item or "")]
    resolved_message_anchor = str(message_anchor or "").strip()
    resolved_physical_order = int(order_key if physical_order is None else physical_order)
    content_basis = {
        "text_payload": resolved_text_payload,
        "image_digest_refs": resolved_image_digest_refs,
        "image_identity_refs": resolved_image_identity_refs,
        "paired_text_ref": paired_text_ref,
        "message_anchor": resolved_message_anchor,
    }
    return {
        "block_id": str(block_id),
        "block_type": str(block_type),
        "stable_hash": _hash_text(f"{block_id}|{resolved_message_anchor}|{paired_text_ref}"),
        "order_key": int(order_key),
        "physical_order": resolved_physical_order,
        "content_hash": _hash_text(json.dumps(content_basis, ensure_ascii=False, sort_keys=True)),
        "text_char_len": len(resolved_text_payload),
        "token_estimate": max(1, len(resolved_text_payload) // 4) if resolved_text_payload else 0,
        "image_digest_refs": resolved_image_digest_refs,
        "image_identity_refs": resolved_image_identity_refs,
        "is_mutable": bool(mutable),
        "source_scope": str(source_scope),
        "section_kind": str(section_kind or "").strip() or _default_section_kind(block_type),
        "message_anchor": resolved_message_anchor,
        "paired_text_ref": str(paired_text_ref or ""),
        "text_payload": resolved_text_payload,
    }


def empty_context_block_plan() -> Dict[str, Any]:
    return {
        "context_block_version": 2,
        "immutable_blocks": [],
        "persona_image_blocks": [],
        "short_memory_blocks": [],
        "stage2_blocks": [],
        "window_blocks": [],
        "window_image_blocks": [],
        "current_turn_blocks": [],
        "blocks": [],
    }


def merge_context_block_plans(*plans: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = empty_context_block_plan()
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        for key in (
            "immutable_blocks",
            "persona_image_blocks",
            "short_memory_blocks",
            "stage2_blocks",
            "window_blocks",
            "window_image_blocks",
            "current_turn_blocks",
            "blocks",
        ):
            values = plan.get(key)
            if isinstance(values, list):
                merged[key].extend(dict(item) for item in values if isinstance(item, dict))
        if isinstance(plan.get("context_block_version"), int):
            merged["context_block_version"] = max(
                int(merged.get("context_block_version") or 1),
                int(plan.get("context_block_version") or 1),
            )
        for key in (
            "upstream_window_size",
            "upstream_window_message_count",
            "upstream_window_image_count",
            "upstream_vision_image_limit",
        ):
            if key in plan:
                merged[key] = int(plan.get(key) or 0)
    return merged
