from __future__ import annotations

from typing import Any


DEFAULT_ADVANCED_USER_ID = "541955254"
DEFAULT_ADVANCED_USER_DISPLAY_NAME = "海泡菜"
DEFAULT_BOT_PERSONA_DISPLAY_NAME = "海菜子"
DEFAULT_PROTECTED_DISPLAY_NAME = DEFAULT_ADVANCED_USER_DISPLAY_NAME


def normalize_advanced_user_id(value: Any) -> str:
    """Normalize configured advanced user ID."""
    return str(value or "").strip() or DEFAULT_ADVANCED_USER_ID


def get_primary_advanced_user_id(system_config: Any | None = None) -> str:
    if system_config is None:
        from holo_cortex_zero.core import config as system_config

    return normalize_advanced_user_id(getattr(system_config, "ADVANCED_USER_ID", None))


def get_primary_advanced_user_display_name(system_config: Any | None = None) -> str:
    if system_config is None:
        from holo_cortex_zero.core import config as system_config

    return str(
        getattr(system_config, "ADVANCED_USER_DISPLAY_NAME", "") or DEFAULT_ADVANCED_USER_DISPLAY_NAME
    ).strip() or DEFAULT_ADVANCED_USER_DISPLAY_NAME


def is_advanced_user_id(user_id: Any, system_config: Any | None = None) -> bool:
    normalized = str(user_id or "").strip()
    return bool(normalized and normalized == get_primary_advanced_user_id(system_config))


def get_bot_persona_display_name(system_config: Any | None = None) -> str:
    if system_config is None:
        from holo_cortex_zero.core import config as system_config

    return str(
        getattr(system_config, "BOT_PERSONA_DISPLAY_NAME", "") or DEFAULT_BOT_PERSONA_DISPLAY_NAME
    ).strip() or DEFAULT_BOT_PERSONA_DISPLAY_NAME
