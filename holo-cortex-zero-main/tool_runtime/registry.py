from __future__ import annotations

from typing import Dict, List, Optional

from .spec import ToolDescriptor


class ToolRuntimeRegistry:
    def __init__(self) -> None:
        self._descriptors: Dict[str, ToolDescriptor] = {}

    def register(self, descriptor: ToolDescriptor) -> None:
        self._descriptors[descriptor.tool_id] = descriptor

    def get(self, tool_id: str) -> Optional[ToolDescriptor]:
        return self._descriptors.get(str(tool_id or "").strip())

    def list_all(self) -> List[ToolDescriptor]:
        return list(self._descriptors.values())
