from __future__ import annotations

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.models.db_context_window import DBContextWindow
from holo_cortex_zero.services.advanced_context_mode import advanced_context_mode_service


def select_main_system_prompt(context_window: DBContextWindow) -> tuple[str, str, bool]:
    selection = advanced_context_mode_service.select_prompt(context_window)
    deep_enabled = bool(selection.mode == "deep")

    logger.info(
        "prompt.selector main prompt selected: "
        f"ctx={context_window.context_id} owner_type={context_window.owner_type} "
        f"effective_mode={selection.mode} mode_source={selection.source} deep_enabled={deep_enabled} "
        f"selected_prompt_key={selection.prompt_key} prompt_length={len(selection.prompt)} "
        f"fallback_used={selection.prompt_fallback_used}"
    )
    return selection.prompt, selection.prompt_key, deep_enabled
