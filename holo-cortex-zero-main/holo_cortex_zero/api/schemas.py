"""Schema 类型定义
"""

from typing import List, Union

from holo_cortex_zero.schemas.agent_ctx import AgentCtx, WebhookRequest
from holo_cortex_zero.schemas.agent_message import (
    AgentMessageSegment,
    AgentMessageSegmentType,
)

__all__ = [
    "AgentCtx",
    "AgentMessageSegment",
    "AgentMessageSegmentType",
    "MessageContent",
    "WebhookRequest",
]

# 消息内容类型
MessageContent = Union[str, List[AgentMessageSegment]]
