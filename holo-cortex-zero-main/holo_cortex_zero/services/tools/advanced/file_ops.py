"""高级维护 Tool 注册层。

具体实现统一收口到 `tool_runtime.tools.file_ops`，本文件只负责：
1. 宿主注册
2. 权限与推荐启用范围
3. 复用统一配置模型
"""
from __future__ import annotations

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.services.tools.registry import tool_registry
from tool_runtime.tools import (
    ADVANCED_TOOL_CATEGORY,
    ADVANCED_TOOL_CONFIG_MODEL,
    APPLY_PATCH_DESCRIPTION,
    APPLY_PATCH_DISPLAY_NAME,
    APPLY_PATCH_PARAMETERS,
    APPLY_PATCH_TOOL_ID,
    LIST_FILES_DESCRIPTION,
    LIST_FILES_DISPLAY_NAME,
    LIST_FILES_PARAMETERS,
    LIST_FILES_TOOL_ID,
    READ_FILE_DESCRIPTION,
    READ_FILE_DISPLAY_NAME,
    READ_FILE_PARAMETERS,
    READ_FILE_TOOL_ID,
    RUN_COMMAND_DESCRIPTION,
    RUN_COMMAND_DISPLAY_NAME,
    RUN_COMMAND_PARAMETERS,
    RUN_COMMAND_TOOL_ID,
    SEARCH_CODE_DESCRIPTION,
    SEARCH_CODE_DISPLAY_NAME,
    SEARCH_CODE_PARAMETERS,
    SEARCH_CODE_TOOL_ID,
    SEND_FILE_DESCRIPTION,
    SEND_FILE_DISPLAY_NAME,
    SEND_FILE_PARAMETERS,
    SEND_FILE_TOOL_ID,
    WRITE_FILE_DESCRIPTION,
    WRITE_FILE_DISPLAY_NAME,
    WRITE_FILE_PARAMETERS,
    WRITE_FILE_TOOL_ID,
    apply_patch,
    list_files,
    read_file,
    run_command,
    search_code,
    send_file,
    write_file,
)


def _register_advanced_tool(*, name: str, display_name: str, description: str, parameters: dict, handler) -> None:
    tool_registry.register(
        name=name,
        display_name=display_name,
        handler=handler,
        description=description,
        parameters=parameters,
        source_kind="privileged",
        capability_class="privileged",
        default_scope="advanced_only",
        permission_level="advanced",
        category=ADVANCED_TOOL_CATEGORY,
        config_model=ADVANCED_TOOL_CONFIG_MODEL,
    )


def register_advanced_tools() -> None:
    """注册所有高级用户 Tool。"""
    for tool_meta in (
        (LIST_FILES_TOOL_ID, LIST_FILES_DISPLAY_NAME, LIST_FILES_DESCRIPTION, LIST_FILES_PARAMETERS, list_files),
        (SEND_FILE_TOOL_ID, SEND_FILE_DISPLAY_NAME, SEND_FILE_DESCRIPTION, SEND_FILE_PARAMETERS, send_file),
        (READ_FILE_TOOL_ID, READ_FILE_DISPLAY_NAME, READ_FILE_DESCRIPTION, READ_FILE_PARAMETERS, read_file),
        (SEARCH_CODE_TOOL_ID, SEARCH_CODE_DISPLAY_NAME, SEARCH_CODE_DESCRIPTION, SEARCH_CODE_PARAMETERS, search_code),
        (RUN_COMMAND_TOOL_ID, RUN_COMMAND_DISPLAY_NAME, RUN_COMMAND_DESCRIPTION, RUN_COMMAND_PARAMETERS, run_command),
        (WRITE_FILE_TOOL_ID, WRITE_FILE_DISPLAY_NAME, WRITE_FILE_DESCRIPTION, WRITE_FILE_PARAMETERS, write_file),
        (APPLY_PATCH_TOOL_ID, APPLY_PATCH_DISPLAY_NAME, APPLY_PATCH_DESCRIPTION, APPLY_PATCH_PARAMETERS, apply_patch),
    ):
        _register_advanced_tool(
            name=tool_meta[0],
            display_name=tool_meta[1],
            description=tool_meta[2],
            parameters=tool_meta[3],
            handler=tool_meta[4],
        )

    logger.info("已注册 7 个高级维护 Tool（纯 Tool Runtime 实现）")
