from __future__ import annotations

from pathlib import Path
from typing import Dict, Type

from pydantic import BaseModel, Field, create_model

from holo_cortex_zero.core.core_utils import ConfigBase, ExtraField
from holo_cortex_zero.core.os_env import OsEnv
from tool_runtime.config import ToolEnabledScope
from tool_runtime.spec import ToolDescriptor


_TOOL_CONFIG_DIR = Path(OsEnv.DATA_DIR) / "configs" / "tools"
_TOOL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
_TOOL_CONFIG_CACHE: Dict[str, ConfigBase] = {}
_TOOL_CONFIG_CLASS_CACHE: Dict[str, Type[ConfigBase]] = {}


class ToolScopeConfig(ConfigBase):
    SCOPE_MODE: ToolEnabledScope = Field(
        default="disabled",
        title="启用范围",
        description="控制该 Tool 在普通/高级上下文中的可见与可执行范围。",
        json_schema_extra=ExtraField(
            i18n_title={"zh-CN": "启用范围", "en-US": "Scope"},
            i18n_description={
                "zh-CN": "disabled / normal_only / advanced_only / all",
                "en-US": "disabled / normal_only / advanced_only / all",
            },
        ).model_dump(),
    )


def _build_tool_config_model(descriptor: ToolDescriptor) -> Type[ConfigBase]:
    cached = _TOOL_CONFIG_CLASS_CACHE.get(descriptor.tool_id)
    if cached is not None:
        return cached

    source_model = descriptor.config_model
    fields: Dict[str, tuple[object, object]] = {
        "SCOPE_MODE": (
            ToolEnabledScope,
            Field(
                default=descriptor.default_scope,
                title="启用范围",
                description="控制该 Tool 在普通/高级上下文中的可见与可执行范围。",
                json_schema_extra=ExtraField(
                    i18n_title={"zh-CN": "启用范围", "en-US": "Scope"},
                    i18n_description={
                        "zh-CN": "disabled / normal_only / advanced_only / all",
                        "en-US": "disabled / normal_only / advanced_only / all",
                    },
                ).model_dump(),
            ),
        )
    }

    for field_name, field_info in source_model.model_fields.items():
        if field_name == "SCOPE_MODE":
            continue
        fields[field_name] = (field_info.annotation, field_info)

    class_name = f"{descriptor.tool_id.title().replace('_', '')}ToolConfig"
    model = create_model(class_name, __base__=ConfigBase, **fields)  # type: ignore[arg-type]
    config_key = f"tool.{descriptor.tool_id}"
    model.set_config_key(config_key)
    model.set_config_file_path(_TOOL_CONFIG_DIR / f"{descriptor.tool_id}.yaml")
    _TOOL_CONFIG_CLASS_CACHE[descriptor.tool_id] = model
    return model


def get_tool_config(descriptor: ToolDescriptor) -> ConfigBase:
    cached = _TOOL_CONFIG_CACHE.get(descriptor.tool_id)
    if cached is not None:
        return cached

    model = _build_tool_config_model(descriptor)
    instance = model.load_config(auto_register=True)
    _TOOL_CONFIG_CACHE[descriptor.tool_id] = instance
    return instance
