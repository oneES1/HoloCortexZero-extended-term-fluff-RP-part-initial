from __future__ import annotations

from holo_cortex_zero.api.schemas import AgentCtx
from holo_cortex_zero.core.logger import logger

from .runtime import inject_memory_prompt


async def collect_memory_recall(ctx: AgentCtx) -> str:
    """系统层 memory recall 入口。

    当前先切主链调用与配置出口，避免继续依赖历史 prompt inject 注册。
    具体 recall 计算仍复用 memory 模块现有实现，后续可继续下沉到系统目录。
    """
    try:
        recall_text = await inject_memory_prompt(ctx)
        return str(recall_text or "").strip()
    except Exception as e:
        logger.error(f"system memory recall 构建失败: {e}", exc_info=True)
        return ""


async def collect_memory_recall_with_meta(ctx: AgentCtx) -> tuple[str, dict[str, object]]:
    """系统层 memory recall 入口（带 Stage1 元信息）。"""
    try:
        try:
            ctx._na_memory_recall_meta = {}
        except Exception:
            pass
        recall_text = await inject_memory_prompt(ctx)
        meta = dict(getattr(ctx, "_na_memory_recall_meta", {}) or {})
        return str(recall_text or "").strip(), meta
    except Exception as e:
        logger.error(f"system memory recall 构建失败: {e}", exc_info=True)
        return "", {}
