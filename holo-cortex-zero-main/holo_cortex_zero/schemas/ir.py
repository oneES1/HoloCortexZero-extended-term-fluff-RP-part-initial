"""中间语义层 (Intermediate Representation)

所有业务逻辑只依赖这些对象，不直接依赖任何下游 API 的 wire format。
协议发射器 (emitter) 负责将 IR 序列化为具体协议格式，
协议解析器 (parser) 负责将下游返回反序列化为 IR。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class MessagePart:
    """消息的一个片段（文本/图片/音频/视频/文件）"""

    type: Literal["text", "image", "audio", "video", "file"]
    text: Optional[str] = None          # type=text 时的文本内容
    url: Optional[str] = None           # type=image/audio/video/file 时的 URL 或宿主机路径
    data: Optional[bytes] = None        # 内联二进制数据（如 base64 解码后的图片）
    mime_type: Optional[str] = None     # MIME 类型
    detail: str = "auto"                # 图片精度（vLLM 要求 input_image 必须带 detail）
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """LLM 发出的 tool 调用"""

    id: str
    name: str
    arguments: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageTurn:
    """一轮消息（对应 chat.completions 的一条 message）"""

    role: Literal["system", "user", "assistant", "tool"]
    parts: List[MessagePart]
    name: Optional[str] = None          # 发送者标识
    tool_call_id: Optional[str] = None  # role=tool 时关联的 call id
    tool_calls: Optional[List[ToolCall]] = None  # role=assistant 时发出的 tool 调用
    reasoning_content: Optional[str] = None  # 支持方需要随 assistant tool_calls 回放的隐藏思考块


@dataclass
class ToolSpec:
    """tool 定义（给 LLM 看的 function schema）"""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    permission_level: Literal["advanced", "normal"] = "normal"


@dataclass
class ToolResult:
    """tool 执行结果"""

    call_id: str
    parts: List[MessagePart]
    is_error: bool = False
    history_role: Literal["tool", "user"] = "tool"
    trace_title: str = ""
    trace_summary: str = ""


@dataclass
class GenerationRequest:
    """发给 LLM 的完整请求（IR → 协议发射器序列化）"""

    context_id: str
    model: str
    messages: List[MessageTurn]
    tools: List[ToolSpec] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)
    # 缓存提示: "static" 区域不变，"dynamic" 区域每次变
    cache_hints: Dict[str, str] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """LLM 返回的完整结果（协议解析器反序列化 → IR）"""

    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    parts: List[MessagePart] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Optional[Dict[str, Any]] = None
    raw_response: Optional[Any] = None  # 原始响应，调试用
    reasoning_content: Optional[str] = None  # 下游返回的隐藏思考块，仅用于后续协议回放
    dump_id: Optional[str] = None  # 请求/响应日志关联 ID，用于精确回溯 prompt dump
