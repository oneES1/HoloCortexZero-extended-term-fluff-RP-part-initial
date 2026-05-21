"""消息相关 API

此模块提供了与消息发送相关的 API 接口。
"""

import time
from typing import Any, Optional, Tuple

from holo_cortex_zero.adapters.utils import adapter_utils
from holo_cortex_zero.api.schemas import AgentCtx
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.schemas.agent_message import (
    AgentMessageSegment,
    AgentMessageSegmentType,
)
from holo_cortex_zero.schemas.chat_message import ChatMessage
from holo_cortex_zero.services.chat.universal_chat_service import universal_chat_service
from holo_cortex_zero.services.message_service import message_service

__all__ = [
    "ChatMessage",
    "send_file",
    "send_image",
    "send_text",
]


async def _resolve_adapter_fast(chat_key: str, ctx: Optional[AgentCtx]) -> Tuple[Any, str]:
    adapter_key = str(getattr(ctx, "adapter_key", "") or "").strip() if ctx else ""
    if adapter_key:
        try:
            return adapter_utils.get_adapter(adapter_key), "ctx"
        except Exception as e:
            logger.warning(
                f"[message_api] adapter fast path fallback: chat_key={chat_key}, adapter_key={adapter_key}, err={e}",
            )

    adapter = await adapter_utils.get_adapter_for_chat(chat_key)
    return adapter, "chat_key_fallback"


async def send_text(
    chat_key: str,
    message: str,
    ctx: AgentCtx,
    *,
    record: bool = True,
    ref_msg_id: Optional[str] = None,
) -> None:
    """发送文本消息

    Args:
        chat_key (str): 聊天标识，格式为 "{adapter_key}-{type}_{id}"，例如 "platform-group_123456"
        message (str): 要发送的文本消息
        ctx (AgentCtx): 上下文对象
        record (bool, optional): 是否记录到上下文。默认为 True

    Example:
        ```python
        from holo_cortex_zero.api.message import send_text

        # 发送文本消息到群组（记录到上下文）
        send_text(chat_key, "你好，世界！", ctx)

        # 发送文本消息到群组（不记录到上下文）
        send_text(chat_key, "这是一条临时消息", ctx, record=False)
        ```
    """
    message_ = [AgentMessageSegment(content=message)]
    started_at = time.monotonic()
    adapter_source = "unknown"
    adapter_lookup_ms = -1.0
    send_forward_ms = -1.0
    record_push_ms = -1.0
    try:
        lookup_started_at = time.monotonic()
        adapter, adapter_source = await _resolve_adapter_fast(chat_key, ctx)
        adapter_lookup_ms = (time.monotonic() - lookup_started_at) * 1000.0

        timing: dict[str, float] = {}
        await universal_chat_service.send_agent_message(
            chat_key,
            message_,
            adapter,
            ctx,
            record=record,
            ref_msg_id=ref_msg_id,
            timing=timing,
        )
        send_forward_ms = float(timing.get("send_forward_ms", -1.0))
        record_push_ms = float(timing.get("record_push_ms", -1.0))
        total_ms = (time.monotonic() - started_at) * 1000.0
        logger.info(
            f"[message_api] send_text chat_key={chat_key} adapter_source={adapter_source} "
            f"adapter_lookup_ms={adapter_lookup_ms:.1f} send_forward_ms={send_forward_ms:.1f} "
            f"record_push_ms={record_push_ms:.1f} total_ms={total_ms:.1f}",
        )
    except Exception as e:
        total_ms = (time.monotonic() - started_at) * 1000.0
        logger.exception(
            f"发送文本消息失败: {e} | chat_key={chat_key} adapter_source={adapter_source} "
            f"adapter_lookup_ms={adapter_lookup_ms:.1f} send_forward_ms={send_forward_ms:.1f} "
            f"record_push_ms={record_push_ms:.1f} total_ms={total_ms:.1f}",
        )
        raise Exception("发送文本消息失败: 请确保聊天标识正确且内容不为空或过长") from e


async def send_file(
    chat_key: str,
    file_path: str,
    ctx: AgentCtx,
    *,
    record: bool = True,
    ref_msg_id: Optional[str] = None,
) -> None:
    """发送文件消息

    Args:
        chat_key (str): 聊天标识，格式为 "{adapter_key}-{type}_{id}"，例如 "platform-group_123456"
        file_path (str): 文件真实绝对路径
        ctx (AgentCtx): 上下文对象
        record (bool, optional): 是否记录到上下文。默认为 True

    Example:
        ```python
        from holo_cortex_zero.api.message import send_file

        # 发送文件（记录到上下文，推荐直接传真实绝对路径）
        send_file(chat_key, "/path/to/file.pdf", ctx)

        # 发送文件（不记录到上下文）
        send_file(chat_key, "/path/to/temp.pdf", ctx, record=False)
        ```
    """
    message_ = [AgentMessageSegment(type=AgentMessageSegmentType.FILE, content=file_path)]
    started_at = time.monotonic()
    adapter_source = "unknown"
    adapter_lookup_ms = -1.0
    send_forward_ms = -1.0
    record_push_ms = -1.0
    try:
        lookup_started_at = time.monotonic()
        adapter, adapter_source = await _resolve_adapter_fast(chat_key, ctx)
        adapter_lookup_ms = (time.monotonic() - lookup_started_at) * 1000.0

        timing: dict[str, float] = {}
        await universal_chat_service.send_agent_message(
            chat_key,
            message_,
            adapter,
            ctx,
            file_mode=True,
            record=record,
            ref_msg_id=ref_msg_id,
            timing=timing,
        )
        send_forward_ms = float(timing.get("send_forward_ms", -1.0))
        record_push_ms = float(timing.get("record_push_ms", -1.0))
        total_ms = (time.monotonic() - started_at) * 1000.0
        logger.info(
            f"[message_api] send_file chat_key={chat_key} adapter_source={adapter_source} "
            f"adapter_lookup_ms={adapter_lookup_ms:.1f} send_forward_ms={send_forward_ms:.1f} "
            f"record_push_ms={record_push_ms:.1f} total_ms={total_ms:.1f}",
        )
    except Exception as e:
        total_ms = (time.monotonic() - started_at) * 1000.0
        logger.exception(
            f"发送文件消息失败: {e} | chat_key={chat_key} adapter_source={adapter_source} "
            f"adapter_lookup_ms={adapter_lookup_ms:.1f} send_forward_ms={send_forward_ms:.1f} "
            f"record_push_ms={record_push_ms:.1f} total_ms={total_ms:.1f}",
        )
        raise Exception(f"发送文件消息失败: {e}") from e


async def send_image(
    chat_key: str,
    image_path: str,
    ctx: AgentCtx,
    *,
    record: bool = True,
    ref_msg_id: Optional[str] = None,
) -> None:
    """发送图片消息

    Args:
        chat_key (str): 聊天标识，格式为 "{adapter_key}-{type}_{id}"，例如 "platform-group_123456"
        image_path (str): 图片真实绝对路径
        ctx (AgentCtx): 上下文对象
        record (bool, optional): 是否记录到上下文。默认为 True

    Example:
        ```python
        from holo_cortex_zero.api.message import send_image

        # 发送图片（记录到上下文，真实绝对路径）
        send_image(chat_key, "/path/to/image.jpg", ctx)

        # 发送图片（不记录到上下文）
        send_image(chat_key, "/path/to/temp.jpg", ctx, record=False)
        ```
    """
    message_ = [AgentMessageSegment(type=AgentMessageSegmentType.FILE, content=image_path)]
    started_at = time.monotonic()
    adapter_source = "unknown"
    adapter_lookup_ms = -1.0
    send_forward_ms = -1.0
    record_push_ms = -1.0
    try:
        lookup_started_at = time.monotonic()
        adapter, adapter_source = await _resolve_adapter_fast(chat_key, ctx)
        adapter_lookup_ms = (time.monotonic() - lookup_started_at) * 1000.0

        timing: dict[str, float] = {}
        await universal_chat_service.send_agent_message(
            chat_key,
            message_,
            adapter,
            ctx,
            record=record,
            ref_msg_id=ref_msg_id,
            timing=timing,
        )
        send_forward_ms = float(timing.get("send_forward_ms", -1.0))
        record_push_ms = float(timing.get("record_push_ms", -1.0))
        total_ms = (time.monotonic() - started_at) * 1000.0
        logger.info(
            f"[message_api] send_image chat_key={chat_key} adapter_source={adapter_source} "
            f"adapter_lookup_ms={adapter_lookup_ms:.1f} send_forward_ms={send_forward_ms:.1f} "
            f"record_push_ms={record_push_ms:.1f} total_ms={total_ms:.1f}",
        )
    except Exception as e:
        total_ms = (time.monotonic() - started_at) * 1000.0
        logger.exception(
            f"发送图片消息失败: {e} | chat_key={chat_key} adapter_source={adapter_source} "
            f"adapter_lookup_ms={adapter_lookup_ms:.1f} send_forward_ms={send_forward_ms:.1f} "
            f"record_push_ms={record_push_ms:.1f} total_ms={total_ms:.1f}",
        )
        raise Exception(f"发送图片消息失败: {e}") from e


async def push_system(
    chat_key: str,
    message: str,
    ctx: Optional[AgentCtx] = None,
    trigger_agent: bool = False,
) -> None:
    """推送系统消息

    Args:
        chat_key (str): 聊天标识，格式为 "{adapter_key}-{channel_id}"，例如 "platform-group_123456"
        message (str): 要推送的系统消息内容。
        ctx (AgentCtx): 上下文对象
        trigger_agent (bool, optional): 是否触发 AI 响应。默认为 False。

    Example:
        ```python
        from holo_cortex_zero.api.message import push_system

        # 推送系统消息并触发 AI 响应
        push_system(chat_key, "Search result of 'xxx' is: xxx. Please check the result.", trigger_agent=True)
    """
    if not ctx:
        ctx = await AgentCtx.create_by_chat_key(chat_key)

    try:
        await message_service.push_system_message(
            chat_key=chat_key,
            agent_messages=message,
            trigger_agent=trigger_agent,
            db_chat_channel=ctx.db_chat_channel,
            ctx=ctx,
        )
    except Exception as e:
        logger.exception(f"发送系统消息失败: {e}")
        raise Exception(f"发送系统消息失败: {e}") from e
