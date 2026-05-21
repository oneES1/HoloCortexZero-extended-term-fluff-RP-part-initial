from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pydantic import BaseModel, Field

from tool_runtime.host import ToolHostBridge, ToolUserLookupResult
from tool_runtime.result import ToolOutcome, ToolPart


ISOLATE_TOOL_ID = "isolate"

ISOLATE_DISPLAY_NAME = "疏远"

ISOLATE_DESCRIPTION = "按用户 ID 疏远该用户"

ISOLATE_PARAMETERS = {
    "type": "object",
    "properties": {
        "user_id": {"type": "string", "description": "目标用户 ID"},
    },
    "required": ["user_id"],
}


class BlockToolConfig(BaseModel):
    MAX_BLOCK_SECONDS: int = Field(
        default=259200,
        title="最大疏远时长（秒）",
        ge=0,
        le=2592000,
        json_schema_extra={"i18n_title": {"zh-CN": "最大疏远时长（秒）", "en-US": "Max Block Duration (seconds)"}},
    )
    DEFAULT_BLOCK_SECONDS: int = Field(
        default=86400,
        title="默认疏远时长（秒）",
        ge=60,
        le=604800,
        json_schema_extra={"i18n_title": {"zh-CN": "默认疏远时长（秒）", "en-US": "Default Block Duration (seconds)"}},
    )


ISOLATE_CONFIG_MODEL = BlockToolConfig


@dataclass
class BlockRecord:
    user_id: str
    platform_userid: str
    username: str
    block_type: str
    reason: str
    start_time: int
    expire_time: int | None
    is_permanent: bool


def _text_outcome(tool_id: str, text: str, *, is_error: bool, trace_summary: str) -> ToolOutcome:
    return ToolOutcome(
        parts=[
            ToolPart(
                type="text",
                text=text,
                meta={"source": "tool", "tool_id": tool_id, "inject_role": "tool"},
            ),
        ],
        is_error=is_error,
        history_role="tool",
        trace_title=f"Tool | {tool_id}",
        trace_summary=trace_summary,
    )


def _now_ts() -> int:
    return int(time.time())


def _normalize_store_records(payload: dict[str, object] | None) -> dict[str, BlockRecord]:
    raw_records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(raw_records, list):
        return {}
    records: dict[str, BlockRecord] = {}
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        try:
            record = BlockRecord(
                user_id=str(item.get("user_id") or "").strip(),
                platform_userid=str(item.get("platform_userid") or "").strip(),
                username=str(item.get("username") or "").strip(),
                block_type=str(item.get("block_type") or "prevent_trigger").strip(),  # type: ignore[arg-type]
                reason=str(item.get("reason") or "").strip(),
                start_time=int(item.get("start_time") or 0),
                expire_time=(int(item["expire_time"]) if item.get("expire_time") not in {None, ""} else None),
                is_permanent=bool(item.get("is_permanent", False)),
            )
        except Exception:
            continue
        if record.user_id:
            records[record.user_id] = record
    return records


def _serialize_records(records: dict[str, BlockRecord]) -> dict[str, object]:
    return {
        "version": 1,
        "updated_at": _now_ts(),
        "records": [asdict(record) for record in records.values()],
    }


def _cleanup_expired(records: dict[str, BlockRecord], *, now_ts: int) -> tuple[dict[str, BlockRecord], int]:
    cleaned: dict[str, BlockRecord] = {}
    removed = 0
    for user_id, record in records.items():
        if not record.is_permanent and record.expire_time is not None and record.expire_time <= now_ts:
            removed += 1
            continue
        cleaned[user_id] = record
    return cleaned, removed


def _resolve_expire_time(config: BlockToolConfig) -> int:
    effective_duration = int(config.DEFAULT_BLOCK_SECONDS)
    if int(config.MAX_BLOCK_SECONDS) > 0:
        effective_duration = min(effective_duration, int(config.MAX_BLOCK_SECONDS))
    return _now_ts() + effective_duration


async def _load_records(tool_host: ToolHostBridge, context_id: str) -> dict[str, BlockRecord]:
    payload = await tool_host.block_store_get(context_id)
    records = _normalize_store_records(payload)
    cleaned, removed = _cleanup_expired(records, now_ts=_now_ts())
    if removed:
        await tool_host.block_store_set(context_id, _serialize_records(cleaned))
    return cleaned


async def _save_records(tool_host: ToolHostBridge, context_id: str, records: dict[str, BlockRecord]) -> None:
    await tool_host.block_store_set(context_id, _serialize_records(records))


async def _resolve_user(tool_host: ToolHostBridge, user_id: str) -> ToolUserLookupResult | None:
    return await tool_host.lookup_user(str(user_id or "").strip())


async def _apply_block(
    *,
    tool_id: str,
    user_id: str,
    tool_host: ToolHostBridge | None,
    tool_config: BlockToolConfig | None,
) -> ToolOutcome:
    config = tool_config or BlockToolConfig()
    if tool_host is None:
        return _text_outcome(tool_id, "Block Tool 缺少宿主桥接。", is_error=True, trace_summary="missing_host")

    target = str(user_id or "").strip()
    if not target:
        return _text_outcome(tool_id, "请提供要操作的用户 ID。", is_error=True, trace_summary="bad_args")

    identity = tool_host.get_context_identity()
    user = await _resolve_user(tool_host, target)
    if user is None:
        return _text_outcome(tool_id, f"未找到用户：{target}", is_error=True, trace_summary="user_not_found")

    expire_time = _resolve_expire_time(config)
    records = await _load_records(tool_host, identity.context_id)
    existing = records.get(user.unique_id)
    if existing and existing.block_type == "full_block":
        return _text_outcome(
            tool_id,
            f"用户 {user.username} 已处于屏蔽状态。",
            is_error=True,
            trace_summary="already_blocked",
        )

    record = BlockRecord(
        user_id=user.unique_id,
        platform_userid=user.platform_userid,
        username=user.username,
        block_type="full_block",
        reason="tool_default",
        start_time=_now_ts(),
        expire_time=expire_time,
        is_permanent=False,
    )
    records[user.unique_id] = record
    await _save_records(tool_host, identity.context_id, records)

    applied = await tool_host.apply_user_block(user.unique_id, block_type="full_block", expire_time=expire_time)
    if not applied:
        records.pop(user.unique_id, None)
        await _save_records(tool_host, identity.context_id, records)
        return _text_outcome(tool_id, f"屏蔽用户 {user.username} 失败，请稍后重试。", is_error=True, trace_summary="apply_failed")

    if existing is not None and existing.block_type != "full_block":
        await tool_host.clear_user_block(user.unique_id, block_type=existing.block_type)

    await tool_host.log(
        "info",
        "block tool applied",
        tool_id=tool_id,
        context_id=identity.context_id,
        user_id=user.unique_id,
        block_type="full_block",
        expire_time=expire_time,
    )
    return _text_outcome(
        tool_id,
        f"已屏蔽用户 {user.username}。",
        is_error=False,
        trace_summary="blocked:full_block",
    )


async def isolate(
    user_id: str,
    tool_host: ToolHostBridge | None = None,
    tool_config: BlockToolConfig | None = None,
) -> ToolOutcome:
    return await _apply_block(
        tool_id=ISOLATE_TOOL_ID,
        user_id=user_id,
        tool_host=tool_host,
        tool_config=tool_config,
    )
