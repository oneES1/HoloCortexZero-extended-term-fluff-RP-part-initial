from __future__ import annotations

from typing import Literal


ToolEnabledScope = Literal["disabled", "normal_only", "advanced_only", "all"]


def scope_allows(*, scope: ToolEnabledScope, permission_level: str) -> bool:
    normalized_permission = str(permission_level or "normal").strip().lower() or "normal"
    if scope == "disabled":
        return False
    if scope == "all":
        return True
    if scope == "advanced_only":
        return normalized_permission == "advanced"
    if scope == "normal_only":
        return normalized_permission != "advanced"
    return False
