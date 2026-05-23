"""通用消息服务

这个服务负责处理跨平台的消息发送逻辑，包含所有与具体协议端无关的通用处理。
协议端特定的逻辑通过 adapter.forward_message 接口委托给各自的适配器实现。
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from holo_cortex_zero.adapters.interface.base import BaseAdapter
from holo_cortex_zero.adapters.interface.schemas.platform import (
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformSendSegment,
    PlatformSendSegmentType,
)
from holo_cortex_zero.api.schemas import AgentCtx
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.schemas.agent_message import (
    AgentMessageSegment,
    AgentMessageSegmentType,
)
from holo_cortex_zero.services.file_system.service import managed_file_service
from holo_cortex_zero.services.agent.resolver import fix_raw_response
from holo_cortex_zero.tools.common_util import download_file, is_url_path

class UniversalChatService:
    """通用消息服务 - 处理跨平台的消息发送逻辑"""

    def __init__(self):
        pass

    async def send_agent_message(
        self,
        chat_key: str,
        messages: Union[List[AgentMessageSegment], str],
        adapter: BaseAdapter,
        ctx: Optional[AgentCtx] = None,
        file_mode: bool = False,
        record: bool = False,
        ref_msg_id: Optional[str] = None,
        timing: Optional[Dict[str, float]] = None,
    ) -> PlatformSendResponse:
        """发送机器人消息

        Args:
            chat_key (str): 聊天的唯一标识
            messages (Union[List[AgentMessageSegment], str]): 机器人消息
            adapter (BaseAdapter): 适配器实例
            ctx (Optional[AgentCtx], optional): 机器人上下文. Defaults to None.
            file_mode (bool, optional): 是否为文件发送模式（影响文件类型的消息段生成）. Defaults to False.
            record (bool, optional): 是否记录聊天记录. Defaults to False.

        Raises:
            ValueError: 聊天类型错误
        """
        if timing is not None:
            timing.setdefault("send_forward_ms", -1.0)
            timing.setdefault("record_push_ms", -1.0)

        def _set_timing(key: str, value: float) -> None:
            if timing is not None:
                timing[key] = value

        if isinstance(messages, str):
            messages = [AgentMessageSegment(type=AgentMessageSegmentType.TEXT, content=messages)]

        # 预处理消息段
        processed_segments = await self._preprocess_messages(messages, chat_key, ctx, file_mode)

        # 检查是否有有效的消息段
        if not processed_segments:
            logger.warning("Empty Message, skip sending")
            return PlatformSendResponse(success=False, error_message="empty message")

        # 构建协议端发送请求
        send_request = PlatformSendRequest(
            chat_key=chat_key,
            segments=processed_segments,
            ref_msg_id=ref_msg_id,
        )

        # 发送消息
        try:
            forward_started_at = time.monotonic()
            plt_response: PlatformSendResponse = await adapter.forward_message(send_request)
            _set_timing("send_forward_ms", (time.monotonic() - forward_started_at) * 1000.0)
        except Exception as e:
            logger.exception(f"发送消息失败: {e}")
            raise

        if not plt_response.success:
            logger.error(f"适配器发送消息失败，错误: {plt_response.error_message}")
            raise ValueError(f"适配器发送消息失败，错误: {plt_response.error_message}")

        # 记录聊天记录
        if record:
            from holo_cortex_zero.services.message_service import message_service

            record_started_at = time.monotonic()
            await message_service.push_bot_message(chat_key, messages, plt_response, ref_msg_id=ref_msg_id)
            _set_timing("record_push_ms", (time.monotonic() - record_started_at) * 1000.0)

        return plt_response

    async def _preprocess_messages(
        self,
        messages: List[AgentMessageSegment],
        chat_key: str,
        ctx: Optional[AgentCtx],
        file_mode: bool,
    ) -> List[PlatformSendSegment]:
        """预处理消息段，将 AgentMessageSegment 转换为 PlatformSendSegment

        Args:
            messages: 原始的 Agent 消息段列表
            chat_key: 聊天频道标识
            ctx: 上下文
            file_mode: 是否为文件模式（用于决定 FILE 类型文件生成 FILE 还是 IMAGE 消息段）

        Returns:
            List[PlatformSendSegment]: 预处理后的平台消息段列表
        """
        processed_segments: List[PlatformSendSegment] = []

        for agent_message in messages:
            content = agent_message.content

            if agent_message.type == AgentMessageSegmentType.TEXT.value:
                # 处理文本消息 - 只做基本的修复，不解析@
                content = fix_raw_response(content)

                if content.strip():
                    processed_segments.append(PlatformSendSegment(type=PlatformSendSegmentType.TEXT, content=content))

                logger.info(f"Sending agent message: {content}")

            elif agent_message.type == AgentMessageSegmentType.FILE.value:
                # 处理文件消息
                try:
                    # 处理URL下载
                    if is_url_path(content):
                        file_path, _ = await download_file(content, from_chat_key=chat_key)
                        processed_file_path = file_path
                        agent_message.content = str(file_path)
                        logger.info(f"高级文件系统出站解析成功: raw={content} kind=url resolved={processed_file_path}")
                    else:
                        processed_file_path, path_kind = managed_file_service.resolve_outbound_local_path(
                            content,
                            chat_key=chat_key,
                            container_key=ctx.container_key if ctx else None,
                        )

                        if processed_file_path:
                            agent_message.content = str(processed_file_path)
                            logger.info(
                                f"高级文件系统出站解析成功: raw={content} kind={path_kind} resolved={processed_file_path}"
                            )
                        else:
                            logger.warning(f"Invalid or non-existent file path: {content}")
                            # 添加错误文本消息
                            processed_segments.append(
                                PlatformSendSegment(type=PlatformSendSegmentType.TEXT, content=f"Invalid file path: {content}"),
                            )
                            continue

                    logger.info(f"Sending agent file: {processed_file_path}")

                    # 根据 file_mode 决定生成 FILE 还是 IMAGE 类型的消息段
                    # 这里只是根据用户意图决定类型，具体的发送方式由协议端决定
                    segment_type = PlatformSendSegmentType.FILE if file_mode else PlatformSendSegmentType.IMAGE

                    processed_segments.append(PlatformSendSegment(type=segment_type, file_path=processed_file_path))

                except ValueError as e:
                    logger.error(f"Path conversion error: {e}")
                    # 添加错误文本消息
                    processed_segments.append(PlatformSendSegment(type=PlatformSendSegmentType.TEXT, content=str(e)))
            else:
                raise ValueError(f"Invalid agent message type: {agent_message.type}")

        return processed_segments


# 全局实例
universal_chat_service = UniversalChatService()
