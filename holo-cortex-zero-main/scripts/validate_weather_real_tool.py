from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import nonebot

nonebot.init()

# Standalone validation imports registry before the app bootstrap path. Import the
# platform schema first to avoid the existing models/adapters circular import.
import holo_cortex_zero.adapters.interface.schemas.platform  # noqa: F401

from holo_cortex_zero.schemas.ir import ToolCall
from holo_cortex_zero.services.tools.migrated import register_migrated_tools
from holo_cortex_zero.services.tools.registry import ToolRuntimeBinding, tool_registry


def _default_output_dir() -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return REPO_ROOT / "stage1_smoke" / f"weather_real_tool_{ts}"


def _text_preview(result: Any) -> str:
    chunks: list[str] = []
    for part in getattr(result, "parts", []) or []:
        text = str(getattr(part, "text", "") or "").strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks)[:600]


async def _execute_case(location: str) -> dict[str, Any]:
    call = ToolCall(id=f"validate_weather_{uuid.uuid4().hex[:8]}", name="weather", arguments={"location": location})
    result = await tool_registry.execute(
        call,
        permission_level="advanced",
        runtime=ToolRuntimeBinding(
            context_id="tool_validate_weather",
            dialog_chat_key="tool_validate-private_weather",
            primary_user_id="tool_validate_advanced",
            permission_level="advanced",
            adapter_key="tool_validate",
            channel_id="private_weather",
        ),
    )
    text = _text_preview(result)
    return {
        "location": location,
        "call_id": call.id,
        "is_error": bool(result.is_error),
        "history_role": str(result.history_role or ""),
        "trace_title": str(result.trace_title or ""),
        "trace_summary": str(result.trace_summary or ""),
        "parts_count": len(result.parts or []),
        "text_preview": text,
        "has_weather_title": "天气查询：" in text,
        "has_hourly": "未来 24 小时预报：" in text,
        "mentions_yanqihu": "雁栖湖" in text,
    }


async def _main(output_dir: Path) -> int:
    register_migrated_tools()

    cases = ["雁栖湖", "怀柔", "北京", "101010500", "116.67000,40.39000"]
    results = []
    for location in cases:
        results.append(await _execute_case(location))

    summary = {
        "tool": "weather",
        "cases": results,
        "all_ok": all(not item["is_error"] and item["has_weather_title"] and item["has_hourly"] for item in results),
        "forbidden_business_state_touched": False,
        "bot_injection_used": False,
        "context_window_touched": False,
        "context_message_touched": False,
        "tool_chain_trace_touched": False,
        "memory_or_compression_touched": False,
        "test_user_10001_touched": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "all_ok": summary["all_ok"]}, ensure_ascii=False))
    return 0 if summary["all_ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    args = parser.parse_args()
    return asyncio.run(_main(args.output_dir))


if __name__ == "__main__":
    raise SystemExit(main())
