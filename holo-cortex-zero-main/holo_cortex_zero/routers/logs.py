from asyncio import Queue
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, Response
from sse_starlette.sse import EventSourceResponse

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import (
    get_log_records,
    get_log_sources,
    logger,
    subscribers,
)
from holo_cortex_zero.schemas.errors import OperationFailedError
from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.services.platform_admin import PlatformAdminPrincipal, get_current_active_platform_admin
from holo_cortex_zero.services.platform_admin import require_platform_role
from holo_cortex_zero.services.user.role import Role

router = APIRouter(prefix="/logs", tags=["Logs"])

# 基础日志来源
DEFAULT_LOG_SOURCES = ["nonebot", "holo_cortex_zero", "uvicorn"]


@router.get("", summary="获取历史日志")
@require_platform_role(Role.Admin)
async def get_logs(
    page: int = 1,
    page_size: int = 500,
    source: Optional[str] = None,
    levels: Optional[str] = None,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取历史日志记录"""
    level_list = [level.strip().upper() for level in str(levels or '').split(',') if level.strip()]
    logs = await get_log_records(page, page_size, source, level_list)
    total = await get_log_records(1, 0, source, level_list, count_only=True)  # 获取总数
    return Ret.success(
        msg="获取成功",
        data={
            "logs": logs,
            "total": total,
        },
    )


@router.get("/sources", summary="获取日志来源列表")
@require_platform_role(Role.Admin)
async def get_sources(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取所有日志来源"""
    sources = await get_log_sources()
    # 合并默认来源和实际来源
    all_sources = sorted(set(DEFAULT_LOG_SOURCES) | set(sources))
    return Ret.success(msg="获取成功", data=all_sources)


@router.get("/stream", summary="实时日志流")
@require_platform_role(Role.Admin)
async def stream_logs(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> EventSourceResponse:
    """获取实时日志流"""
    try:

        async def event_generator() -> AsyncGenerator[str, None]:
            queue: Queue = Queue()
            subscribers.append(queue)
            try:
                while True:
                    message = await queue.get()
                    yield message
            finally:
                subscribers.remove(queue)

        return EventSourceResponse(event_generator())
    except Exception as e:
        logger.error(f"日志流异常: {e!s}")
        raise OperationFailedError(operation="建立日志流", detail=str(e)) from e


@router.get("/download", summary="下载最近日志")
@require_platform_role(Role.Admin)
async def download_logs(
    lines: int = 1000,
    source: Optional[str] = None,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Response:
    """下载最近的日志文件

    Args:
        lines: 要下载的日志行数
        source: 日志来源过滤

    Returns:
        日志文件下载响应
    """
    try:
        # 限制最大下载行数，避免系统负载过大
        max_lines = min(lines, 10000)

        # 获取日志记录，确保返回的是列表
        logs = await get_log_records(page=1, page_size=max_lines, source=source, count_only=False)
        if not isinstance(logs, list):
            logger.error(f"获取日志记录返回了非列表类型: {type(logs)}")
            logs = []

        # 将日志转换为文本格式
        log_text = ""
        for log in logs:
            log_text += (
                f"[{log['timestamp']}] [{log['level']}] {log['source']} | {log['function']}:{log['line']} | {log['message']}\n"
            )

        # 生成文件名，包含时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        source_part = f"_{source}" if source else ""
        filename = f"holo_cortex_zero_logs{source_part}_{timestamp}.txt"

        # 创建响应
        response = Response(content=log_text, media_type="text/plain")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    except Exception as e:
        logger.error(f"下载日志失败: {e!s}")
        raise OperationFailedError(operation="下载日志", detail=str(e)) from e
    else:
        return response
