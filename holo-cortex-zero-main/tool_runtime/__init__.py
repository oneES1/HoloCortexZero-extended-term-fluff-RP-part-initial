"""Pure Tool Runtime core.

主干约束：本包不允许依赖 `holo_cortex_zero.*`，仅承载 Tool 抽象、配置和注册语义。
"""

from .config import ToolEnabledScope
from .host import ToolHostBridge
from .registry import ToolRuntimeRegistry
from .result import ToolOutcome, ToolPart
from .spec import ToolCapabilityClass, ToolDescriptor

__all__ = [
    "ToolCapabilityClass",
    "ToolDescriptor",
    "ToolEnabledScope",
    "ToolHostBridge",
    "ToolOutcome",
    "ToolPart",
    "ToolRuntimeRegistry",
]
