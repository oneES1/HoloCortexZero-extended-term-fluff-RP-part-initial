from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from tool_runtime.host import ToolHostBridge
from tool_runtime.result import ToolOutcome, ToolPart


ADVANCED_TOOL_CATEGORY = "高级维护"
ADVANCED_TOOL_TRACE_TITLE = "Tool | advanced_file_ops"

LIST_FILES_TOOL_ID = "list_files"
SEND_FILE_TOOL_ID = "send_file"
READ_FILE_TOOL_ID = "read_file"
SEARCH_CODE_TOOL_ID = "search_code"
RUN_COMMAND_TOOL_ID = "run_command"
WRITE_FILE_TOOL_ID = "write_file"
APPLY_PATCH_TOOL_ID = "apply_patch"

LIST_FILES_DISPLAY_NAME = "查看文件结构"
SEND_FILE_DISPLAY_NAME = "发送文件"
READ_FILE_DISPLAY_NAME = "读取文件"
SEARCH_CODE_DISPLAY_NAME = "搜索代码"
RUN_COMMAND_DISPLAY_NAME = "执行命令"
WRITE_FILE_DISPLAY_NAME = "写入文件"
APPLY_PATCH_DISPLAY_NAME = "应用补丁"

LIST_FILES_DESCRIPTION = "查看目录文件结构，支持深度限制与文件名模式过滤。"
SEND_FILE_DESCRIPTION = "把宿主机真实本地绝对路径对应的图片或文件发送到当前对话窗口。"
READ_FILE_DESCRIPTION = "读取文本文件内容，支持指定起止行号。"
SEARCH_CODE_DESCRIPTION = "按关键词或正则搜索代码，返回命中的文件名与行号。"
RUN_COMMAND_DESCRIPTION = "在允许目录执行白名单命令，返回退出码与输出。"

_DEFAULT_PROJECT_ROOT = str(Path(os.environ.get("HCZ_WORKSPACE_ROOT") or os.environ.get("WORKSPACE_ROOT") or "/workspace"))
WRITE_FILE_DESCRIPTION = "写入或创建文本文件，禁止写入敏感凭据文件。"
APPLY_PATCH_DESCRIPTION = "对文本文件执行一次最小替换补丁，命中第一处 old_text。"

LIST_FILES_PARAMETERS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "要查看的目录路径，相对于项目根目录或绝对路径。"},
        "max_depth": {"type": "integer", "description": "最大递归深度，默认 3。"},
        "pattern": {"type": "string", "description": "文件名过滤模式，支持 glob，默认 *。"},
    },
    "required": ["path"],
}
SEND_FILE_PARAMETERS = {
    "type": "object",
    "properties": {
        "file_path": {"type": "string", "description": "要发送到当前窗口的真实本地绝对路径。"},
        "ref_msg_id": {"type": "string", "description": "可选的引用消息 ID。"},
    },
    "required": ["file_path"],
}
READ_FILE_PARAMETERS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "文件路径。"},
        "start_line": {"type": "integer", "description": "起始行号，从 1 开始，默认 1。"},
        "end_line": {"type": "integer", "description": "结束行号，默认读到文件末尾。"},
    },
    "required": ["path"],
}
SEARCH_CODE_PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "搜索关键词或正则表达式。"},
        "path": {"type": "string", "description": "搜索目录，默认项目根目录。"},
        "file_pattern": {"type": "string", "description": "文件名过滤模式，例如 *.py。"},
        "max_results": {"type": "integer", "description": "最大返回结果数，默认 20。"},
    },
    "required": ["query"],
}
RUN_COMMAND_PARAMETERS = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "要执行的命令，必须匹配白名单前缀。"},
        "cwd": {"type": "string", "description": "工作目录，默认项目根目录。"},
        "timeout": {"type": "integer", "description": "超时秒数，默认 60。"},
    },
    "required": ["command"],
}
WRITE_FILE_PARAMETERS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "文件路径。"},
        "content": {"type": "string", "description": "完整文件内容。"},
    },
    "required": ["path", "content"],
}
APPLY_PATCH_PARAMETERS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "文件路径。"},
        "old_text": {"type": "string", "description": "要替换的原始文本片段。"},
        "new_text": {"type": "string", "description": "替换后的新文本。"},
    },
    "required": ["path", "old_text", "new_text"],
}

_DEFAULT_ALLOWED_COMMAND_PREFIXES = [
    "git ", "ls ", "cat ", "head ", "tail ", "grep ", "rg ",
    "find ", "wc ", "diff ", "file ",
    "pytest ", "python ", "pip ", "pip3 ",
    "npm ", "npx ", "node ", "yarn ", "pnpm ",
    "docker ", "docker-compose ",
    "curl ", "wget ",
    "du ", "df ",
    "env ", "echo ",
    "make ", "cargo ", "go ",
    "systemctl status",
]
_DEFAULT_BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"dd\s+if=",
    r"mkfs",
    r"shutdown",
    r"reboot",
    r">\s*/dev/sd",
    r"curl\s+.*\|\s*(?:ba)?sh",
    r"wget\s+.*\|\s*(?:ba)?sh",
]


class AdvancedToolConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    PROJECT_ROOT: str = Field(
        default=_DEFAULT_PROJECT_ROOT,
        title="项目根目录",
        json_schema_extra={"i18n_title": {"zh-CN": "项目根目录", "en-US": "Project Root"}},
    )
    DEFAULT_TIMEOUT: int = Field(
        default=60,
        title="默认命令超时(秒)",
        ge=1,
        le=300,
        json_schema_extra={"i18n_title": {"zh-CN": "默认命令超时(秒)", "en-US": "Default Command Timeout (seconds)"}},
    )
    ALLOWED_COMMAND_PREFIXES: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_ALLOWED_COMMAND_PREFIXES),
        title="允许命令前缀",
        json_schema_extra={"i18n_title": {"zh-CN": "允许命令前缀", "en-US": "Allowed Command Prefixes"}},
    )
    BLOCKED_PATTERNS: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_BLOCKED_PATTERNS),
        title="危险命令正则",
        json_schema_extra={"i18n_title": {"zh-CN": "危险命令正则", "en-US": "Dangerous Command Regex"}},
    )


ADVANCED_TOOL_CONFIG_MODEL = AdvancedToolConfig


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
        trace_title=ADVANCED_TOOL_TRACE_TITLE,
        trace_summary=trace_summary,
    )


def _missing_host(tool_id: str) -> ToolOutcome:
    return _text_outcome(tool_id, f"{tool_id} 缺少宿主桥接。", is_error=True, trace_summary="missing_host")


def _looks_like_error(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True
    prefixes = (
        "错误:",
        "命令被拒绝:",
        "工作目录错误:",
        "执行错误:",
        "命令执行超时",
        "文件不存在:",
        "读取错误:",
        "搜索错误:",
        "写入错误:",
        "修补错误:",
        "未找到要替换的文本片段",
        "安全限制:",
    )
    return normalized.startswith(prefixes)


def _result_outcome(tool_id: str, text: str, *, trace_summary: str) -> ToolOutcome:
    return _text_outcome(tool_id, text, is_error=_looks_like_error(text), trace_summary=trace_summary)


def _allowed_prefixes(config: AdvancedToolConfig) -> Sequence[str]:
    prefixes = [str(item or "").strip() for item in config.ALLOWED_COMMAND_PREFIXES]
    return tuple(item for item in prefixes if item)


def _blocked_patterns(config: AdvancedToolConfig) -> Sequence[str]:
    patterns = [str(item or "").strip() for item in config.BLOCKED_PATTERNS]
    return tuple(item for item in patterns if item)


async def list_files(
    path: str = ".",
    max_depth: int = 3,
    pattern: str = "*",
    tool_host: ToolHostBridge | None = None,
    tool_config: AdvancedToolConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _missing_host(LIST_FILES_TOOL_ID)
    config = tool_config or AdvancedToolConfig()
    result = await tool_host.list_files(
        str(path or "."),
        max_depth=max(0, int(max_depth or 0)),
        pattern=str(pattern or "*") or "*",
        project_root=str(config.PROJECT_ROOT or ""),
    )
    return _result_outcome(LIST_FILES_TOOL_ID, result, trace_summary=LIST_FILES_TOOL_ID)


async def send_file(
    file_path: str,
    ref_msg_id: str = "",
    tool_host: ToolHostBridge | None = None,
    tool_config: AdvancedToolConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _missing_host(SEND_FILE_TOOL_ID)
    result = await tool_host.send_file(str(file_path or "").strip(), ref_msg_id=str(ref_msg_id or "").strip())
    return _result_outcome(SEND_FILE_TOOL_ID, result, trace_summary=SEND_FILE_TOOL_ID)


async def read_file(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
    tool_host: ToolHostBridge | None = None,
    tool_config: AdvancedToolConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _missing_host(READ_FILE_TOOL_ID)
    config = tool_config or AdvancedToolConfig()
    result = await tool_host.read_text_file(
        str(path or "").strip(),
        start_line=max(1, int(start_line or 1)),
        end_line=(max(1, int(end_line)) if end_line is not None else None),
        project_root=str(config.PROJECT_ROOT or ""),
    )
    return _result_outcome(READ_FILE_TOOL_ID, result, trace_summary=READ_FILE_TOOL_ID)


async def search_code(
    query: str,
    path: str = ".",
    file_pattern: str = "",
    max_results: int = 20,
    tool_host: ToolHostBridge | None = None,
    tool_config: AdvancedToolConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _missing_host(SEARCH_CODE_TOOL_ID)
    config = tool_config or AdvancedToolConfig()
    result = await tool_host.search_text(
        str(query or "").strip(),
        path=str(path or "."),
        file_pattern=str(file_pattern or ""),
        max_results=max(1, int(max_results or 1)),
        project_root=str(config.PROJECT_ROOT or ""),
    )
    return _result_outcome(SEARCH_CODE_TOOL_ID, result, trace_summary=SEARCH_CODE_TOOL_ID)


async def run_command(
    command: str,
    cwd: str = "",
    timeout: int = 60,
    tool_host: ToolHostBridge | None = None,
    tool_config: AdvancedToolConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _missing_host(RUN_COMMAND_TOOL_ID)
    config = tool_config or AdvancedToolConfig()
    requested_timeout = int(timeout or config.DEFAULT_TIMEOUT or 60)
    result = await tool_host.run_command(
        str(command or "").strip(),
        cwd=str(cwd or "").strip(),
        timeout=max(1, requested_timeout),
        project_root=str(config.PROJECT_ROOT or ""),
        allowed_prefixes=_allowed_prefixes(config),
        blocked_patterns=_blocked_patterns(config),
    )
    return _result_outcome(RUN_COMMAND_TOOL_ID, result, trace_summary=RUN_COMMAND_TOOL_ID)


async def write_file(
    path: str,
    content: str,
    tool_host: ToolHostBridge | None = None,
    tool_config: AdvancedToolConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _missing_host(WRITE_FILE_TOOL_ID)
    config = tool_config or AdvancedToolConfig()
    result = await tool_host.write_text_file(
        str(path or "").strip(),
        str(content or ""),
        project_root=str(config.PROJECT_ROOT or ""),
    )
    return _result_outcome(WRITE_FILE_TOOL_ID, result, trace_summary=WRITE_FILE_TOOL_ID)


async def apply_patch(
    path: str,
    old_text: str,
    new_text: str,
    tool_host: ToolHostBridge | None = None,
    tool_config: AdvancedToolConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _missing_host(APPLY_PATCH_TOOL_ID)
    config = tool_config or AdvancedToolConfig()
    result = await tool_host.apply_text_patch(
        str(path or "").strip(),
        str(old_text or ""),
        str(new_text or ""),
        project_root=str(config.PROJECT_ROOT or ""),
    )
    return _result_outcome(APPLY_PATCH_TOOL_ID, result, trace_summary=APPLY_PATCH_TOOL_ID)
