"""协议发射器基类

每个具体发射器负责：
1. IR → 下游 wire format (emit)
2. 下游响应 → IR (parse)
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

from holo_cortex_zero.schemas.ir import (
    GenerationRequest,
    GenerationResult,
    MessagePart,
    MessageTurn,
    ToolCall,
    ToolSpec,
)


@dataclass(frozen=True)
class EmitterMediaCapabilities:
    """发射器对主干公开的只读媒体能力声明。"""

    name: str
    accepts_image_parts: bool
    accepts_audio_parts: bool
    accepts_video_parts: bool
    native_tool_calling: bool
    notes: str = ""


class BaseEmitter(abc.ABC):
    """协议发射器抽象基类"""

    @abc.abstractmethod
    def get_media_capabilities(self) -> EmitterMediaCapabilities:
        """返回发射器支持的媒体 / tool 能力声明。"""
        ...

    @abc.abstractmethod
    async def generate(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GenerationResult:
        """非流式调用"""
        ...

    @abc.abstractmethod
    async def generate_stream(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[GenerationResult, None]:
        """流式调用，yield 增量 GenerationResult"""
        ...
        # make it async generator
        yield  # type: ignore[misc]

    # ── 通用工具方法 ──

    @staticmethod
    def _text_parts_to_string(parts: List[MessagePart]) -> str:
        """将 MessagePart 列表中的文本拼成纯字符串"""
        return "".join(p.text or "" for p in parts if p.type == "text")

    @staticmethod
    def _degrade_media_part(part: MessagePart) -> MessagePart:
        """将不支持的媒体 part 降级为文本描述"""
        if part.type == "audio":
            fname = (part.url or "audio").rsplit("/", 1)[-1]
            return MessagePart(type="text", text=f"[音频: {fname}]")
        if part.type == "video":
            fname = (part.url or "video").rsplit("/", 1)[-1]
            return MessagePart(type="text", text=f"[视频: {fname}]")
        if part.type == "file":
            fname = (part.url or "file").rsplit("/", 1)[-1]
            return MessagePart(type="text", text=f"[文件: {fname}]")
        return part
