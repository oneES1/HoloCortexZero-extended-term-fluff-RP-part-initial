import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from holo_cortex_zero.core.os_env import PROMPT_LOG_DIR
from holo_cortex_zero.services.llm.reasoning_text import build_reasoning_content, extract_text_reasoning_content
from holo_cortex_zero.models.db_tool_chain_trace import DBToolChainTrace, ToolChainTraceStopType
from holo_cortex_zero.schemas.errors import NotFoundError
from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.services.platform_admin import PlatformAdminPrincipal, get_current_active_platform_admin
from holo_cortex_zero.services.platform_admin import require_platform_role
from holo_cortex_zero.services.user.role import Role

router = APIRouter(prefix="/tool-traces", tags=["ToolTraces"])

def _extract_response_reasoning_content(response_payload: Dict[str, Any]) -> Optional[str]:
    candidates: list[str] = []

    choices = response_payload.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            reasoning_content = message.get("reasoning_content")
            if isinstance(reasoning_content, str) and reasoning_content.strip():
                candidates.append(reasoning_content.strip())

    output = response_payload.get("output")
    if isinstance(output, list):
        reasoning_items = [dict(item) for item in output if isinstance(item, dict) and item.get("type") == "reasoning"]
        text_reasoning_content: Optional[str] = None
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict) or content.get("type") != "output_text":
                    continue
                _, extracted = extract_text_reasoning_content(content.get("text"))
                if extracted:
                    text_reasoning_content = extracted
        reasoning_content = build_reasoning_content(
            text=text_reasoning_content,
            responses_items=reasoning_items,
            origin_protocol="responses" if reasoning_items or text_reasoning_content else "",
        )
        if reasoning_content:
            candidates.append(reasoning_content)

    gemini_signatures: list[str] = []
    candidates_payload = response_payload.get("candidates")
    if isinstance(candidates_payload, list):
        for candidate in candidates_payload:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content") or {}
            parts = content.get("parts") if isinstance(content, dict) else None
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                signature = part.get("thoughtSignature") or part.get("thought_signature")
                if isinstance(signature, str) and signature.strip():
                    gemini_signatures.append(signature.strip())
                if bool(part.get("thought")):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        candidates.append(text.strip())
    gemini_content = build_reasoning_content(
        gemini_thought_signatures=gemini_signatures,
        origin_protocol="gemini" if gemini_signatures else "",
    )
    if gemini_content:
        candidates.append(gemini_content)

    if not candidates:
        return None
    return max(candidates, key=len)


def _trace_has_reasoning_content(payload: Dict[str, Any]) -> bool:
    raw_rounds = payload.get("llm_rounds")
    if isinstance(raw_rounds, list):
        for round_data in raw_rounds:
            if not isinstance(round_data, dict):
                continue
            reasoning_content = round_data.get("reasoning_content")
            if isinstance(reasoning_content, str) and reasoning_content.strip():
                return True

    raw_events = payload.get("events")
    if isinstance(raw_events, list):
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            if str(event.get("kind") or "") != "llm":
                continue
            reasoning_content = event.get("reasoning_content")
            if isinstance(reasoning_content, str) and reasoning_content.strip():
                return True

    return False


def _read_response_reasoning_by_dump_id(prompt_dir: Path, dump_id: str) -> Optional[str]:
    normalized_dump_id = str(dump_id or "").strip()
    if not normalized_dump_id:
        return None

    response_path = prompt_dir / f"v2_response_{normalized_dump_id}.json"
    if not response_path.exists():
        return None

    try:
        with response_path.open("r", encoding="utf-8") as file_handle:
            response_payload = json.load(file_handle)
    except Exception:
        return None

    if not isinstance(response_payload, dict):
        return None
    return _extract_response_reasoning_content(response_payload)


def _enrich_trace_reasoning_from_prompt_logs(log: DBToolChainTrace, payload: Dict[str, Any]) -> Dict[str, Any]:
    if _trace_has_reasoning_content(payload):
        return payload

    prompt_dir = Path(PROMPT_LOG_DIR)
    if not prompt_dir.exists():
        return payload

    raw_rounds = payload.get("llm_rounds")
    raw_events = payload.get("events")
    if not isinstance(raw_rounds, list) or not isinstance(raw_events, list):
        return payload

    llm_event_indexes = [
        index
        for index, event in enumerate(raw_events)
        if isinstance(event, dict) and str(event.get("kind") or "") == "llm"
    ]

    for round_index, round_data in enumerate(raw_rounds):
        if not isinstance(round_data, dict):
            continue
        if str(round_data.get("reasoning_content") or "").strip():
            continue
        dump_id = str(round_data.get("dump_id") or "").strip()
        if not dump_id and round_index < len(llm_event_indexes):
            event = raw_events[llm_event_indexes[round_index]]
            if isinstance(event, dict):
                dump_id = str(event.get("dump_id") or "").strip()
        reasoning_content = _read_response_reasoning_by_dump_id(prompt_dir, dump_id)
        if not reasoning_content:
            continue

        round_data["reasoning_content"] = reasoning_content
        if round_index < len(llm_event_indexes):
            event = raw_events[llm_event_indexes[round_index]]
            if isinstance(event, dict) and not str(event.get("reasoning_content") or "").strip():
                event["reasoning_content"] = reasoning_content

    return payload


def _parse_trace_json(trace_json: str) -> Dict[str, Any]:
    if not trace_json:
        return {}
    try:
        payload = json.loads(trace_json)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


@router.get("/logs", summary="获取新架构 Tool 链运行日志")
@require_platform_role(Role.Admin)
async def get_tool_trace_logs(
    page: int = 1,
    page_size: int = 20,
    chat_key: Optional[str] = None,
    success: Optional[bool] = None,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取新架构 Tool 链运行日志列表"""
    query = DBToolChainTrace.all()

    if chat_key:
        query = query.filter(trigger_chat_key=chat_key)
    if success is not None:
        query = query.filter(success=success)

    total = await query.count()
    logs = await query.order_by("-create_time").offset((page - 1) * page_size).limit(page_size)

    return Ret.success(
        msg="获取成功",
        data={
            "total": total,
            "items": [
                {
                    "id": log.id,
                    "context_id": log.context_id,
                    "chat_key": log.trigger_chat_key,
                    "active_dialog_id": log.active_dialog_id,
                    "permission_level": log.permission_level,
                    "trigger_user_id": log.trigger_user_id,
                    "trigger_user_name": log.trigger_user_name,
                    "trigger_message_text": log.trigger_message_text,
                    "summary_text": log.summary_text,
                    "success": log.success,
                    "create_time": log.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "stop_type": int(log.stop_type),
                    "llm_duration_ms": log.llm_duration_ms,
                    "tool_duration_ms": log.tool_duration_ms,
                    "total_duration_ms": log.total_duration_ms,
                    "total_iterations": log.total_iterations,
                    "use_model": log.use_model,
                    "token_input": log.token_input,
                    "token_output": log.token_output,
                    "token_total": log.token_total,
                    "trace_data": _parse_trace_json(log.trace_json),
                }
                for log in logs
            ],
        },
    )


@router.get("/log-content", summary="获取新架构 Tool 链运行日志详情")
@require_platform_role(Role.Admin)
async def get_tool_trace_log_content(
    trace_id: int,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> JSONResponse:
    """根据运行记录 ID 获取完整运行轨迹 JSON"""
    log = await DBToolChainTrace.filter(id=trace_id).first()
    if not log:
        raise NotFoundError(resource="Trace log")
    payload = _parse_trace_json(log.trace_json)
    payload = _enrich_trace_reasoning_from_prompt_logs(log, payload)
    return JSONResponse(content=payload)


@router.get("/stats", summary="获取新架构 Tool 链运行统计")
@require_platform_role(Role.Admin)
async def get_tool_trace_stats(
    recent: int = 500,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取新架构 Tool 链统计信息（默认最近 500 条）"""
    recent_ids = await DBToolChainTrace.all().order_by("-create_time").limit(recent).values_list("id", flat=True)
    if not recent_ids:
        return Ret.success(
            msg="获取成功",
            data={"total": 0, "success": 0, "failed": 0, "success_rate": 0, "agent_count": 0},
        )

    total = len(recent_ids)
    success = await DBToolChainTrace.filter(id__in=recent_ids, success=True).count()
    failed = await DBToolChainTrace.filter(id__in=recent_ids, success=False).count()
    agent_count = await DBToolChainTrace.filter(id__in=recent_ids, stop_type=ToolChainTraceStopType.AGENT).count()

    return Ret.success(
        msg="获取成功",
        data={
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 2) if total > 0 else 0,
            "agent_count": agent_count,
        },
    )
