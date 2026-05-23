from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import PROMPT_LOG_DIR


def _jsonable(data: Any) -> Any:
    if hasattr(data, "model_dump"):
        try:
            return data.model_dump(mode="json")
        except Exception:
            try:
                return data.model_dump()
            except Exception:
                pass
    if isinstance(data, dict):
        return {str(key): _jsonable(value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [_jsonable(item) for item in data]
    return data


def _safe_name(value: Any, *, fallback: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return fallback
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in raw)
    safe = safe.strip("._-")
    if not safe:
        return fallback
    return safe[:80]


def _build_dump_id(*, protocol: str, payload: Any) -> str:
    model = payload.get("model") if isinstance(payload, dict) else None
    safe_protocol = _safe_name(protocol, fallback="unknown_protocol")
    safe_model = _safe_name(model, fallback="unknown_model")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{safe_protocol}_{safe_model}_{timestamp}"


def _append_suffix(dump_id: str, suffix: Optional[str]) -> str:
    if not suffix:
        return dump_id
    safe_suffix = _safe_name(suffix, fallback="extra")
    return f"{dump_id}_{safe_suffix}"


def dump_prompt_json(
    *,
    kind: str,
    protocol: str,
    payload: Any,
    dump_id: Optional[str] = None,
    suffix: Optional[str] = None,
) -> tuple[str, str]:
    log_dir = Path(PROMPT_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    final_dump_id = _append_suffix(dump_id or _build_dump_id(protocol=protocol, payload=payload), suffix)
    log_path = log_dir / f"v2_{kind}_{final_dump_id}.json"

    with log_path.open("w", encoding="utf-8") as dump_file:
        json.dump(_jsonable(payload), dump_file, ensure_ascii=False, indent=2, default=str)

    logger.debug(f"[llm][{protocol}] {kind} dumped to {log_path}")
    return str(log_path), final_dump_id


def dump_prompt_request(
    *,
    protocol: str,
    payload: Any,
    dump_id: Optional[str] = None,
    suffix: Optional[str] = None,
) -> tuple[str, str]:
    return dump_prompt_json(kind="request", protocol=protocol, payload=payload, dump_id=dump_id, suffix=suffix)


def dump_prompt_response(
    *,
    protocol: str,
    payload: Any,
    dump_id: str,
    suffix: Optional[str] = None,
) -> tuple[str, str]:
    return dump_prompt_json(kind="response", protocol=protocol, payload=payload, dump_id=dump_id, suffix=suffix)
