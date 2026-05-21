from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv


_MEMORY_LOG_ROOT = Path(OsEnv.DATA_DIR) / "logs" / "memory"


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
        return {str(k): _jsonable(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_jsonable(item) for item in data]
    return data


def dump_memory_json(scope: str, kind: str, payload: Dict[str, Any]) -> str:
    log_dir = _MEMORY_LOG_ROOT / scope
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    unique = uuid.uuid4().hex[:8]
    log_path = log_dir / f"{kind}_{ts}_{unique}.json"
    with log_path.open("w", encoding="utf-8") as f:
        json.dump(_jsonable(payload), f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"[memory][{scope}] {kind} dumped to {log_path}")
    return str(log_path)
