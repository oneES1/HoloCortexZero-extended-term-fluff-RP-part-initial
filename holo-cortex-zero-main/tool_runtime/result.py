from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class ToolPart:
    type: Literal["text", "image", "audio", "video", "file"]
    text: Optional[str] = None
    url: Optional[str] = None
    data: Optional[bytes] = None
    mime_type: Optional[str] = None
    detail: str = "auto"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutcome:
    parts: List[ToolPart] = field(default_factory=list)
    is_error: bool = False
    history_role: Literal["tool", "user"] = "tool"
    trace_title: str = ""
    trace_summary: str = ""
