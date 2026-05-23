from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ToolSourceKind = Literal["system", "migrated", "privileged"]


@dataclass(frozen=True)
class ToolAccessSnapshot:
    scope_mode: str
    effective_normal_enabled: bool
    effective_advanced_enabled: bool
