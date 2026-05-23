"""新架构初始化

在应用启动时调用，负责：
1. 注册系统 Tool 与特权 Tool
2. 恢复上下文窗口状态
3. 加载 Tool 配置与执行参数
4. 启动 timeline 等系统服务
"""
from __future__ import annotations

import asyncio

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.runtime_identity import get_primary_advanced_user_id


_MEMORY_INIT_RETRY_DELAY_SECONDS = 5


async def _initialize_memory_runtime_with_single_retry() -> None:
    """初始化 memory 运行时；首次失败时等待 5 秒后重试一次。"""
    from holo_cortex_zero.services.memory import auto_memory_service, initialize_memory_runtime

    try:
        await initialize_memory_runtime()
        await auto_memory_service.initialize_runtime()
        return
    except Exception as exc:
        logger.warning(
            "memory runtime init failed on first attempt; retry once after %ss: %s",
            _MEMORY_INIT_RETRY_DELAY_SECONDS,
            exc,
        )

    await asyncio.sleep(_MEMORY_INIT_RETRY_DELAY_SECONDS)
    await initialize_memory_runtime()
    await auto_memory_service.initialize_runtime()


async def init_new_architecture() -> None:
    """初始化新架构的所有组件"""
    logger.info("初始化新架构组件...")

    # 1. Tool 注册是本地描述与 YAML 配置加载，必须先于 memory/Qdrant/timeline 等运行时依赖完成。
    from holo_cortex_zero.services.moment import system_moment_service
    from holo_cortex_zero.services.tools.advanced.file_ops import register_advanced_tools
    from holo_cortex_zero.services.tools.migrated import register_migrated_tools
    from holo_cortex_zero.services.tools.registry import tool_registry

    system_moment_service.register_tools_once()
    register_advanced_tools()
    register_migrated_tools()
    logger.info(f"Tool 注册阶段完成: total={tool_registry.tool_count}")

    # 2. 完成 context_window schema 自补，避免后续运行时查询 DBContextWindow 时旧表缺列
    from holo_cortex_zero.services.context_window.manager import context_window_manager
    await context_window_manager.ensure_schema_columns()

    # 2.1 完成 memory schema 自补与系统记忆初始化。
    await _initialize_memory_runtime_with_single_retry()

    # 2.2 清理普通用户图片隔离区中过期文件
    from holo_cortex_zero.services.file_system.quarantine import quarantine_file_service
    quarantine_file_service.cleanup_expired()

    # 2.3 恢复上下文窗口状态
    await context_window_manager.on_restart_recover()

    # 3. 初始化系统级语音 / 表情 / moment 服务，并提前关闭旧残留运行时
    from holo_cortex_zero.services.ai_reply import system_ai_reply_service
    from holo_cortex_zero.services.system_emoji import system_emoji_service
    from holo_cortex_zero.services.the_deep import system_the_deep_service
    from holo_cortex_zero.services.system_voice import system_voice_service
    await system_ai_reply_service.initialize_runtime()
    await system_emoji_service.initialize_runtime()
    await system_voice_service.initialize_runtime()
    await system_moment_service.initialize_runtime()
    await system_the_deep_service.initialize_runtime()

    # 4. 加载配置
    _load_config()

    # 5. 启动内置 Timeline 压缩服务
    from holo_cortex_zero.services.context_window.timeline import timeline_service
    timeline_service.start()

    visible_tools = tool_registry.get_tools_for_context("advanced")
    skipped = [n for n, t in tool_registry._tools.items() if t.skip_llm_tool]
    logger.success(
        f"新架构初始化完成: "
        f"{tool_registry.tool_count} total, {len(visible_tools)} visible to LLM, "
        f"skipped={skipped}"
    )


def _load_config() -> None:
    """从全局配置加载新架构参数"""
    from holo_cortex_zero.services.context_window.manager import context_window_manager
    from holo_cortex_zero.services.context_window.timeline import timeline_service
    from holo_cortex_zero.services.tools.chain_executor import tool_chain_executor

    # 高级用户身份只从系统配置主干读取。
    context_window_manager.advanced_user_id = get_primary_advanced_user_id(config)
    context_window_manager.group_chat_max_inject = 8

    tool_chain_executor.max_callbacks = 50
    tool_chain_executor.total_timeout_seconds = 300.0
    tool_chain_executor.consecutive_empty_limit = 3

    # Timeline 压缩服务配置：未配置模型组时跳过压缩，不阻断开源首次启动。
    timeline_group = str(getattr(config, "TIMELINE_MODEL_GROUP", "") or "").strip()
    model_groups = getattr(config, "MODEL_GROUPS", {}) or {}
    if not timeline_group:
        timeline_service.summary_model_group = ""
        logger.warning("Timeline 压缩未启用：TIMELINE_MODEL_GROUP 为空。")
        return
    if timeline_group not in model_groups:
        timeline_service.summary_model_group = ""
        logger.warning("Timeline 压缩未启用：模型组 %s 不存在。", timeline_group)
        return
    timeline_service.summary_model_group = timeline_group
    timeline_service.llm_max_tokens = 3000
    timeline_service.llm_timeout_seconds = 600.0
