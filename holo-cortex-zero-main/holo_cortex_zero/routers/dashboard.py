import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from tortoise.functions import Avg, Count

from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.models.db_chat_message import DBChatMessage
from holo_cortex_zero.models.db_tool_chain_trace import DBToolChainTrace, ToolChainTraceStopType
from holo_cortex_zero.schemas.chat_message import ChatType
from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.services.platform_admin import PlatformAdminPrincipal, get_current_active_platform_admin

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


DASHBOARD_HISTORY_POINTS = 50
MAX_DASHBOARD_WINDOW_MINUTES = 60 * 24 * 365


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _tool_call_count_from_trace(trace: DBToolChainTrace) -> int:
    try:
        payload = json.loads(trace.trace_json or "{}")
    except (TypeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    diagnostics = payload.get("diagnostics")
    if isinstance(diagnostics, dict):
        tool_call_count = _non_negative_int(diagnostics.get("tool_calls_executed_total"))
        if tool_call_count > 0:
            return tool_call_count

    events = payload.get("events")
    if not isinstance(events, list):
        return 0
    return sum(1 for event in events if isinstance(event, dict) and event.get("kind") == "tool")


def _sum_tool_call_count(traces: List[DBToolChainTrace]) -> int:
    return sum(_tool_call_count_from_trace(trace) for trace in traces)


def _success_run_count(traces: List[DBToolChainTrace]) -> int:
    return sum(1 for trace in traces if trace.success)


def align_time_floor(dt: datetime, bucket_minutes: int) -> datetime:
    interval_seconds = bucket_minutes * 60
    aligned_timestamp = (int(dt.timestamp()) // interval_seconds) * interval_seconds
    return datetime.fromtimestamp(aligned_timestamp)


async def get_time_range(time_range: str = "day", window_minutes: Optional[int] = None) -> datetime:
    now = datetime.now()
    if window_minutes is not None:
        return now - timedelta(minutes=window_minutes)
    if time_range == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if time_range == "week":
        start_time = now - timedelta(days=now.weekday())
        return start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    if time_range == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(days=1)


@router.get("/overview", summary="获取仪表盘概览数据")
async def get_dashboard_overview(
    time_range: str = "day",
    window_minutes: Optional[int] = Query(None, ge=1, le=MAX_DASHBOARD_WINDOW_MINUTES),
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    start_time = await get_time_range(time_range, window_minutes)

    total_messages = await DBChatMessage.filter(create_time__gte=start_time).count()
    active_sessions = len(
        await DBChatMessage.filter(
            create_time__gte=start_time,
        )
        .distinct()
        .values_list("chat_key", flat=True),
    )
    unique_users = await DBChatMessage.filter(create_time__gte=start_time).distinct().values_list("sender_id", flat=True)
    tool_chain_traces = await DBToolChainTrace.filter(create_time__gte=start_time).all()
    total_tool_chain_runs = _sum_tool_call_count(tool_chain_traces)
    total_tool_chain_run_records = len(tool_chain_traces)
    success_calls = _success_run_count(tool_chain_traces)
    failed_calls = max(0, total_tool_chain_run_records - success_calls)
    success_rate = round(success_calls / total_tool_chain_run_records * 100, 2) if total_tool_chain_run_records > 0 else 0

    return Ret.success(
        msg="获取成功",
        data={
            "total_messages": total_messages,
            "active_sessions": active_sessions,
            "unique_users": len(unique_users),
            "total_tool_chain_runs": total_tool_chain_runs,
            "success_calls": success_calls,
            "failed_calls": failed_calls,
            "success_rate": success_rate,
        },
    )


@router.get("/trends", summary="获取趋势数据")
async def get_trends(
    metrics: str,
    time_range: str = "day",
    interval: str = "hour",
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取趋势数据"""
    # 计算时间范围
    now = datetime.now()
    if time_range == "day":
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if interval == "hour":
            intervals = 24
            delta = timedelta(hours=1)
        else:
            intervals = 24
            delta = timedelta(hours=1)
    elif time_range == "week":
        start_time = now - timedelta(days=now.weekday())
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        if interval == "day":
            intervals = 7
            delta = timedelta(days=1)
        else:
            intervals = 7 * 24
            delta = timedelta(hours=1)
    elif time_range == "month":
        start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if interval == "day":
            intervals = 30
            delta = timedelta(days=1)
        else:
            intervals = 30
            delta = timedelta(days=1)
    else:
        start_time = now - timedelta(days=1)
        intervals = 24
        delta = timedelta(hours=1)

    # 解析请求的指标
    metrics_list = metrics.split(",")

    # 准备结果数据
    result = []
    current_time = start_time

    for _ in range(intervals):
        next_time = current_time + delta
        data_point: Dict[str, Union[str, int, float]] = {"timestamp": current_time.isoformat()}

        # 查询各指标数据
        if "messages" in metrics_list:
            messages_count = await DBChatMessage.filter(create_time__gte=current_time, create_time__lt=next_time).count()
            data_point["messages"] = messages_count

        if any(m in metrics_list for m in ["tool_chain_runs", "success_calls", "failed_calls", "success_rate"]):
            tool_chain_traces = await DBToolChainTrace.filter(
                create_time__gte=current_time,
                create_time__lt=next_time,
            ).all()
            tool_chain_runs = _sum_tool_call_count(tool_chain_traces)
            tool_chain_run_records = len(tool_chain_traces)

            if "tool_chain_runs" in metrics_list:
                data_point["tool_chain_runs"] = tool_chain_runs

            if any(m in metrics_list for m in ["success_calls", "failed_calls", "success_rate"]):
                success_calls = _success_run_count(tool_chain_traces)

                if "success_calls" in metrics_list:
                    data_point["success_calls"] = success_calls

                if "failed_calls" in metrics_list:
                    data_point["failed_calls"] = max(0, tool_chain_run_records - success_calls)

                if "success_rate" in metrics_list:
                    data_point["success_rate"] = round(success_calls / tool_chain_run_records * 100, 2) if tool_chain_run_records > 0 else 0

        result.append(data_point)
        current_time = next_time

    return Ret.success(
        msg="获取成功",
        data=result,
    )


@router.get("/ranking", summary="获取排名数据")
async def get_ranking(
    ranking_type: str,
    time_range: str = "day",
    limit: int = 10,
    window_minutes: Optional[int] = Query(None, ge=1, le=MAX_DASHBOARD_WINDOW_MINUTES),
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    start_time = await get_time_range(time_range, window_minutes)

    if ranking_type == "users":
        execs = await DBToolChainTrace.filter(
            create_time__gte=start_time,
            trigger_user_id__not_in=["0", "-1", ""],  # 过滤掉系统触发的执行
        ).all()

        user_counts = {}
        for _exec in execs:
            user_id = _exec.trigger_user_id
            user_name = _exec.trigger_user_name

            if user_id not in user_counts:
                user_counts[user_id] = {
                    "id": user_id,
                    "name": user_name,
                    "value": 0,
                }

            user_counts[user_id]["value"] += 1

        result = sorted(user_counts.values(), key=lambda x: x["value"], reverse=True)[:limit]

        return Ret.success(
            msg="获取成功",
            data=result,
        )

    return Ret.success(
        msg="获取成功",
        data=[],
    )


@router.get("/stats/stream", summary="获取实时统计数据流")
async def get_stats_stream(
    granularity: int = Query(10, description="数据粒度（分钟）", ge=1, le=MAX_DASHBOARD_WINDOW_MINUTES),
    window_minutes: Optional[int] = Query(None, description="时间窗口（分钟）", ge=1, le=MAX_DASHBOARD_WINDOW_MINUTES),
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
):
    bucket_minutes = granularity
    history_window_minutes = granularity * DASHBOARD_HISTORY_POINTS
    if window_minutes is not None:
        history_window_minutes = window_minutes
        bucket_minutes = max(1, (window_minutes + DASHBOARD_HISTORY_POINTS - 1) // DASHBOARD_HISTORY_POINTS)

    async def generate():
        try:
            last_message_count = await DBChatMessage.all().count()

            start_time = datetime.now() - timedelta(minutes=history_window_minutes)
            current_time = align_time_floor(start_time, bucket_minutes)

            while current_time < datetime.now():
                next_time = current_time + timedelta(minutes=bucket_minutes)

                messages = await DBChatMessage.filter(
                    create_time__gte=current_time,
                    create_time__lt=next_time,
                ).count()

                execs = await DBToolChainTrace.filter(
                    create_time__gte=current_time,
                    create_time__lt=next_time,
                ).all()

                tool_chain_runs = _sum_tool_call_count(execs)
                success_calls = _success_run_count(execs)
                failed_calls = max(0, len(execs) - success_calls)
                avg_exec_time = sum(_exec.total_duration_ms for _exec in execs) / len(execs) if execs else 0

                yield json.dumps(
                    {
                        "timestamp": current_time.isoformat(),
                        "recent_messages": messages,
                        "recent_tool_chain_runs": tool_chain_runs,
                        "recent_success_calls": success_calls,
                        "recent_failed_calls": failed_calls,
                        "recent_avg_exec_time": round(avg_exec_time, 2),
                    },
                )
                await asyncio.sleep(0.01)

                current_time = next_time

            now = datetime.now()
            next_aligned_time = align_time_floor(now, bucket_minutes) + timedelta(minutes=bucket_minutes)

            while True:
                wait_seconds = (next_aligned_time - datetime.now()).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                current_message_count = await DBChatMessage.all().count()

                recent_messages = current_message_count - last_message_count
                bucket_start = next_aligned_time - timedelta(minutes=bucket_minutes)

                recent_execs = await DBToolChainTrace.filter(
                    create_time__gte=bucket_start,
                    create_time__lt=next_aligned_time,
                ).all()
                recent_tool_chain_runs = _sum_tool_call_count(recent_execs)
                recent_success_calls = _success_run_count(recent_execs)
                recent_failed_calls = max(0, len(recent_execs) - recent_success_calls)
                recent_avg_exec_time = (
                    sum(_exec.total_duration_ms for _exec in recent_execs) / len(recent_execs) if recent_execs else 0
                )

                last_message_count = current_message_count

                yield json.dumps(
                    {
                        "timestamp": next_aligned_time.isoformat(),
                        "recent_messages": recent_messages,
                        "recent_tool_chain_runs": recent_tool_chain_runs,
                        "recent_success_calls": recent_success_calls,
                        "recent_failed_calls": recent_failed_calls,
                        "recent_avg_exec_time": round(recent_avg_exec_time, 2),
                    },
                )

                next_aligned_time = next_aligned_time + timedelta(minutes=bucket_minutes)

        except Exception as e:
            print(f"Stream error: {e}")
            yield json.dumps({"error": str(e)})

    return EventSourceResponse(generate())


@router.get("/distributions", summary="获取所有分布数据")
async def get_distributions(
    time_range: str = "day",
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    start_time = await get_time_range(time_range)

    total_execs = await DBToolChainTrace.filter(create_time__gte=start_time).count()
    stop_type_data = []

    if total_execs > 0:
        for stop_type in ToolChainTraceStopType:
            count = await DBToolChainTrace.filter(create_time__gte=start_time, stop_type=stop_type).count()
            if count > 0:
                stop_type_data.append(
                    {
                        "label": stop_type.value,
                        "value": count,
                        "percentage": round(count / total_execs * 100, 2),
                    },
                )

    total_messages = await DBChatMessage.filter(create_time__gte=start_time).count()
    message_type_data = []

    if total_messages > 0:
        group_count = await DBChatMessage.filter(create_time__gte=start_time, chat_type=ChatType.GROUP).count()
        private_count = await DBChatMessage.filter(create_time__gte=start_time, chat_type=ChatType.PRIVATE).count()
        unknown_count = await DBChatMessage.filter(create_time__gte=start_time, chat_type=ChatType.UNKNOWN).count()

        message_type_data = [
            {
                "label": "群聊消息",
                "value": group_count,
                "percentage": round(group_count / total_messages * 100, 2),
            },
            {
                "label": "私聊消息",
                "value": private_count,
                "percentage": round(private_count / total_messages * 100, 2),
            },
            {
                "label": "未知来源",
                "value": unknown_count,
                "percentage": round(unknown_count / total_messages * 100, 2),
            },
        ]

    return Ret.success(
        msg="获取成功",
        data={
            "stop_type": stop_type_data,
            "message_type": message_type_data,
        },
    )


@router.get("/latest-message", summary="获取最新LLM消息")
async def get_latest_message(
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    message = await DBChatMessage.filter(sender_id="-1").order_by("-create_time").first()
    if not message:
        return Ret.success(msg="暂无消息", data=None)

    return Ret.success(
        msg="获取成功",
        data={
            "id": message.id,
            "sender_name": message.sender_name,
            "content": message.content_text,
            "create_time": message.create_time.isoformat() if message.create_time else None,
            "chat_key": message.chat_key,
        },
    )
