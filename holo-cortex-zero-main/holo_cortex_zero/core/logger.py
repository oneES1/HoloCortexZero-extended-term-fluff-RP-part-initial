import json
import re
import sys
from asyncio import Queue
from collections import deque
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import AsyncGenerator, Dict, List, Optional, Set

from loguru import logger

from .config import config
from .os_env import APP_LOG_DIR

# 内存中保存最近的日志记录
log_records = deque(maxlen=1000)
# 订阅者队列
subscribers: List[Queue] = []
# 记录所有出现过的日志来源
log_sources: Set[str] = set()


APP_LOG_TAIL_READ_BYTES = 5 * 1024 * 1024
APP_LOG_FILE_RECORD_LIMIT = 1000
LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(?P<level>[A-Z]+)\] (?P<source>.+?) \| (?P<function>[^:|]+):(?P<line>\d+)\| (?P<message>.*)$"
)


def _normalize_file_timestamp(value: str) -> str:
    current_year = datetime.now().year
    return f"{current_year}-{value}"


def _log_record_key(log: Dict) -> str:
    return "|".join(
        [
            str(log.get("timestamp", "")),
            str(log.get("level", "")),
            str(log.get("source", "")),
            str(log.get("function", "")),
            str(log.get("line", "")),
            str(log.get("message", "")),
        ]
    )


def _parse_log_text(log_text: str) -> List[Dict]:
    records: List[Dict] = []
    current: Optional[Dict] = None

    for raw_line in log_text.splitlines():
        line = raw_line.rstrip("\n")
        matched = LOG_LINE_PATTERN.match(line)
        if matched:
            if current:
                records.append(current)
            current = {
                "timestamp": _normalize_file_timestamp(matched.group("timestamp")),
                "level": matched.group("level"),
                "message": matched.group("message"),
                "source": matched.group("source"),
                "function": matched.group("function"),
                "line": int(matched.group("line")),
            }
            continue

        if current is not None and line.strip():
            current["message"] = f"{current['message']}\n{line}"

    if current:
        records.append(current)
    return records


def _read_file_log_tail(path: Path) -> List[Dict]:
    if not path.exists() or not path.is_file():
        return []

    file_size = path.stat().st_size
    if file_size <= 0:
        return []

    read_size = min(file_size, APP_LOG_TAIL_READ_BYTES)
    with path.open("rb") as file:
        file.seek(-read_size, 2)
        payload = file.read(read_size)

    if file_size > read_size:
        first_newline = payload.find(b"\n")
        if first_newline >= 0:
            payload = payload[first_newline + 1 :]

    parsed = _parse_log_text(payload.decode("utf-8", errors="ignore"))
    if len(parsed) > APP_LOG_FILE_RECORD_LIMIT:
        return parsed[-APP_LOG_FILE_RECORD_LIMIT:]
    return parsed


def format_log_entry(record: Dict) -> Dict:
    """格式化日志条目"""
    # 记录日志来源
    log_sources.add(record["name"])

    return {
        "timestamp": datetime.fromtimestamp(record["time"].timestamp()).strftime("%Y-%m-%d %H:%M:%S"),
        "level": record["level"].name,
        "message": record["message"],
        "source": record["name"],
        "function": record["function"],
        "line": record["line"],
    }


class LogInterceptHandler:
    """日志拦截处理器"""

    async def __call__(self, message):
        """处理日志消息"""
        record = message.record
        log_entry = format_log_entry(record)
        log_records.append(log_entry)
        log_json = json.dumps(log_entry)
        for queue in subscribers:
            await queue.put(f"{log_json}\n\n")


# 捕获未处理的异常处理
def exception_handler(
    _type: BaseException,
    value: BaseException,
    traceback: TracebackType,  # noqa: ARG001
):
    try:
        raise value  # noqa: TRY301
    except Exception:
        logger.exception("Uncaught exception occurred")


sys.excepthook = exception_handler

# 立即配置日志处理器
log_handlers = [
    {
        "sink": LogInterceptHandler(),
        "format": (
            "<g>{time:MM-DD HH:mm:ss}</g> "
            "[<lvl>{level}</lvl>] "
            "<c><u>{name}</u></c> | "
            "<c>{function}:{line}</c>| "
            "{message}"
        ),
        "level": config.APP_LOG_LEVEL,
    },
    {
        "sink": sys.stdout,
        "format": (
            "<g>{time:MM-DD HH:mm:ss}</g> "
            "[<lvl>{level}</lvl>] "
            "<c><u>{name}</u></c> | "
            "<c>{function}:{line}</c>| "
            "{message}"
        ),
        "level": config.APP_LOG_LEVEL,
    },
    {
        "sink": Path(APP_LOG_DIR) / "app.log",
        "format": (
            "<g>{time:MM-DD HH:mm:ss}</g> "
            "[<lvl>{level}</lvl>] "
            "<c><u>{name}</u></c> | "
            "<c>{function}:{line}</c>| "
            "{message}"
        ),
        "level": config.APP_LOG_LEVEL,
        "rotation": "100 MB",
        "retention": "10 days",
        "compression": "zip",
    },
]

logger.configure(handlers=log_handlers) # type: ignore


async def get_log_records(
    page: int = 1,
    page_size: int = 100,
    source: Optional[str] = None,
    levels: Optional[List[str]] = None,
    count_only: bool = False,
) -> List[Dict] | int:
    """获取历史日志记录，默认返回最新的100条日志

    Args:
        page: 页码，从1开始
        page_size: 每页记录数
        source: 日志来源过滤
        count_only: 是否只返回计数

    Returns:
        返回指定页的日志记录，按时间从新到旧排序
    """
    normalized_levels = {str(level or '').strip().upper() for level in (levels or []) if str(level or '').strip()}

    memory_logs = [
        log
        for log in log_records
        if (not source or log["source"] == source)
        and (not normalized_levels or str(log.get("level", "")).upper() in normalized_levels)
    ]

    file_logs = [
        log
        for log in _read_file_log_tail(Path(APP_LOG_DIR) / "app.log")
        if (not source or log["source"] == source)
        and (not normalized_levels or str(log.get("level", "")).upper() in normalized_levels)
    ]

    merged_map: Dict[str, Dict] = {}
    for log in file_logs:
        merged_map[_log_record_key(log)] = log
    for log in memory_logs:
        merged_map[_log_record_key(log)] = log

    merged_logs = sorted(merged_map.values(), key=lambda item: str(item.get("timestamp", "")))

    if count_only:
        return len(merged_logs)

    newest_first = merged_logs[::-1]
    start = (page - 1) * page_size
    end = start + page_size if page_size > 0 else None
    return newest_first[start:end][::-1]


async def get_log_sources() -> List[str]:
    """获取所有日志来源"""
    return sorted(log_sources)


async def subscribe_logs() -> AsyncGenerator[str, None]:
    """订阅日志流"""
    queue: Queue = Queue()
    subscribers.append(queue)
    try:
        while True:
            message = await queue.get()
            yield message
    finally:
        subscribers.remove(queue)
