"""Migrated Tool registrations.

历史能力迁为纯 Tool Runtime 后，统一在这里接入宿主注册层。
"""

from __future__ import annotations

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.services.tools.registry import tool_registry
from tool_runtime.tools import (
    ISOLATE_CONFIG_MODEL,
    ISOLATE_DESCRIPTION,
    ISOLATE_DISPLAY_NAME,
    ISOLATE_PARAMETERS,
    ISOLATE_TOOL_ID,
    GIF_GENERATION_CONFIG_MODEL,
    GIF_GENERATION_DESCRIPTION,
    GIF_GENERATION_DISPLAY_NAME,
    GIF_GENERATION_PARAMETERS,
    LIGHTROOM_CONFIG_MODEL,
    LIGHTROOM_DESCRIPTION,
    LIGHTROOM_DISPLAY_NAME,
    LIGHTROOM_PARAMETERS,
    MAGIC_DRAW_SHARED_CATEGORY,
    PHOTOSHOP_CONFIG_MODEL,
    PHOTOSHOP_DESCRIPTION,
    PHOTOSHOP_DISPLAY_NAME,
    PHOTOSHOP_PARAMETERS,
    WEBSEARCH_CONFIG_MODEL,
    WEBSEARCH_DESCRIPTION,
    WEBSEARCH_DISPLAY_NAME,
    WEBSEARCH_PARAMETERS,
    WEBSEARCH_TOOL_ID,
    WEATHER_CONFIG_MODEL,
    WEATHER_DESCRIPTION,
    WEATHER_DISPLAY_NAME,
    WEATHER_PARAMETERS,
    WEATHER_TOOL_ID,
    isolate,
    gif_generation,
    lightroom,
    photoshop,
    websearch,
    weather,
)


def _register_magic_draw_tools() -> None:
    for name, display_name, description, parameters, handler, config_model in (
        ("gif_generation", GIF_GENERATION_DISPLAY_NAME, GIF_GENERATION_DESCRIPTION, GIF_GENERATION_PARAMETERS, gif_generation, GIF_GENERATION_CONFIG_MODEL),
        ("photoshop", PHOTOSHOP_DISPLAY_NAME, PHOTOSHOP_DESCRIPTION, PHOTOSHOP_PARAMETERS, photoshop, PHOTOSHOP_CONFIG_MODEL),
        ("lightroom", LIGHTROOM_DISPLAY_NAME, LIGHTROOM_DESCRIPTION, LIGHTROOM_PARAMETERS, lightroom, LIGHTROOM_CONFIG_MODEL),
    ):
        tool_registry.register(
            name=name,
            display_name=display_name,
            handler=handler,
            description=description,
            parameters=parameters,
            source_kind="migrated",
            capability_class="user_facing",
            default_scope="all",
            supports_multimodal_return=True,
            category=MAGIC_DRAW_SHARED_CATEGORY,
            config_model=config_model,
        )


def register_migrated_tools() -> None:
    tool_registry.register(
        name=WEATHER_TOOL_ID,
        display_name=WEATHER_DISPLAY_NAME,
        handler=weather,
        description=WEATHER_DESCRIPTION,
        parameters=WEATHER_PARAMETERS,
        source_kind="migrated",
        capability_class="user_facing",
        default_scope="all",
        config_model=WEATHER_CONFIG_MODEL,
    )
    tool_registry.register(
        name=WEBSEARCH_TOOL_ID,
        display_name=WEBSEARCH_DISPLAY_NAME,
        handler=websearch,
        description=WEBSEARCH_DESCRIPTION,
        parameters=WEBSEARCH_PARAMETERS,
        source_kind="migrated",
        capability_class="user_facing",
        default_scope="all",
        config_model=WEBSEARCH_CONFIG_MODEL,
    )
    tool_registry.register(
        name=ISOLATE_TOOL_ID,
        display_name=ISOLATE_DISPLAY_NAME,
        handler=isolate,
        description=ISOLATE_DESCRIPTION,
        parameters=ISOLATE_PARAMETERS,
        source_kind="migrated",
        capability_class="user_facing",
        default_scope="all",
        config_model=ISOLATE_CONFIG_MODEL,
    )
    _register_magic_draw_tools()
    logger.info("已注册迁移 Tool: weather, websearch, isolate, magic_draw_*")
