from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Literal, Type

from pydantic import BaseModel

from .config import ToolEnabledScope
from .result import ToolOutcome


ToolCapabilityClass = Literal["user_facing", "privileged"]
ToolHandler = Callable[..., Awaitable[ToolOutcome]]


@dataclass(frozen=True)
class ToolDescriptor:
    tool_id: str
    display_name: str
    description: str
    category: str
    capability_class: ToolCapabilityClass
    default_scope: ToolEnabledScope
    parameters_schema: Dict[str, Any]
    supports_multimodal_return: bool
    config_model: Type[BaseModel]
    handler: ToolHandler
