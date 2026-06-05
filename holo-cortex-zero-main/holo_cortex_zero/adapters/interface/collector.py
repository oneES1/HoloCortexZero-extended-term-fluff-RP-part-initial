import time
from typing import TYPE_CHECKING, Optional

from holo_cortex_zero.adapters.interface.identity import canonicalize_inbound_identity
from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.models.db_user import DBUser
from holo_cortex_zero.schemas.chat_message import ChatMessage
from holo_cortex_zero.services.file_system.policy import resolve_incoming_attachment_mode
from holo_cortex_zero.services.media_link import fetch_netease_audio_from_message
from holo_cortex_zero.schemas.user import UserCreate
from holo_cortex_zero.services.message_service import message_service
from holo_cortex_zero.services.user.util import user_register

if TYPE_CHECKING:
    from holo_cortex_zero.adapters.interface import (
        BaseAdapter,
        PlatformChannel,
        PlatformMessage,
        PlatformUser,
    )


async def collect_message(
    adapter: "BaseAdapter",
    platform_channel: "PlatformChannel",
    platform_user: "PlatformUser",
    platform_message: "PlatformMessage",
    trigger_agent: bool = False,
) -> None:
    """适配器消息收集器"""
    canonical = canonicalize_inbound_identity(
        adapter=adapter,
        platform_user=platform_user,
        platform_channel=platform_channel,
        platform_message=platform_message,
    )
    platform_user = canonical.platform_user
    platform_channel = canonical.platform_channel
    platform_message = canonical.platform_message
    trigger_requested = bool(trigger_agent)
    trigger_agent = bool(trigger_requested and canonical.is_primary_advanced_user)

    logger.info(
        "adapter_identity canonicalized: "
        "adapter=%s raw_user=%s canonical_user=%s raw_channel=%s canonical_channel=%s "
        "chat_type=%s identity_mapped=%s native_voice=%s trigger_requested=%s trigger_effective=%s",
        adapter.key,
        canonical.raw_platform_userid,
        canonical.canonical_userid,
        canonical.raw_channel_id,
        canonical.canonical_channel_id,
        getattr(platform_channel.channel_type, "value", platform_channel.channel_type),
        canonical.identity_mapped,
        bool(platform_message.ext_data and platform_message.ext_data.native_voice),
        trigger_requested,
        trigger_agent,
    )

    sender_name = str(platform_user.user_name or "").strip()
    sender_nickname = str(platform_message.sender_nickname or "").strip()
    sanitized_sender_name, sanitized_sender_nickname, identity_sanitized = message_service._sanitize_protected_sender_identity(
        user_id=platform_user.user_id,
        sender_name=sender_name,
        sender_nickname=sender_nickname,
    )
    if identity_sanitized:
        logger.warning(
            "适配器入口检测到受保护昵称伪装，已在注册前清洗: adapter=%s user_id=%s raw_sender_name=%r raw_sender_nickname=%r sanitized=%s",
            adapter.key,
            platform_user.user_id,
            sender_name,
            sender_nickname,
            sanitized_sender_name,
        )

    db_chat_channel: DBChatChannel = await DBChatChannel.get_or_create(
        adapter_key=adapter.key,
        channel_id=platform_channel.channel_id,
        channel_type=platform_channel.channel_type,
        channel_name=platform_channel.channel_name,
    )

    if not db_chat_channel.is_active:
        return

    # 用户处理
    user: Optional[DBUser] = await DBUser.get_by_union_id(adapter_key=adapter.key, platform_userid=platform_user.user_id)

    if not user:
        ret = await user_register(
            UserCreate(
                username=sanitized_sender_name,
                adapter_key=adapter.key,
                platform_userid=platform_user.user_id,
            ),
        )

        if not ret:
            logger.error(f"注册用户失败: {sanitized_sender_name} - {platform_user.user_id}")
            return

        user = await DBUser.get_by_union_id(adapter_key=adapter.key, platform_userid=platform_user.user_id)
        assert user

    if not user.is_active:
        logger.info(f"用户 {platform_user.user_id} 被封禁，封禁结束时间: {user.ban_until}")
        return

    if platform_message.is_self:
        logger.info(f'接收自身消息 "{platform_message.content_text}"，跳过...')
        return

    if canonical.is_primary_advanced_user:
        channel_type_value = getattr(platform_channel.channel_type, "value", platform_channel.channel_type)
        ingest_mode, ingest_reason = resolve_incoming_attachment_mode(
            adapter_key=adapter.key,
            chat_key=db_chat_channel.chat_key,
            chat_type=str(channel_type_value or ""),
            sender_id=platform_user.user_id,
            platform_userid=platform_user.user_id,
            attachment_kind="audio",
            channel_type=str(channel_type_value or ""),
        )
        if ingest_mode == "managed":
            max_bytes = int(getattr(config, "MAX_UPLOAD_SIZE_MB", 10) or 10) * 1024 * 1024
            audio_segment = await fetch_netease_audio_from_message(
                platform_message,
                from_chat_key=db_chat_channel.chat_key,
                max_bytes=max_bytes,
            )
            if audio_segment:
                platform_message.content_data.append(audio_segment)
                logger.info(
                    "netease audio segment appended: adapter=%s chat_type=%s mode=%s reason=%s",
                    adapter.key,
                    channel_type_value,
                    ingest_mode,
                    ingest_reason,
                )

    chat_message: ChatMessage = ChatMessage(
        message_id=platform_message.message_id,
        sender_id=platform_user.user_id,
        sender_name=sanitized_sender_name,
        sender_nickname=sanitized_sender_nickname,
        adapter_key=adapter.key,
        platform_userid=platform_user.user_id,
        is_tome=platform_message.is_tome,
        is_recalled=False,
        chat_key=db_chat_channel.chat_key,
        chat_type=platform_channel.channel_type,
        content_text=platform_message.content_text,
        content_data=platform_message.content_data,
        ext_data=platform_message.ext_data.model_dump() if platform_message.ext_data else {},
        send_timestamp=int(time.time()),
    )

    ref_str: str = (
        f" (ref: {platform_message.ext_data.ref_msg_id})"
        if platform_message.ext_data and platform_message.ext_data.ref_msg_id
        else ""
    )

    logger.info(
        f"Message Collect: [{chat_message.chat_key}] {platform_user.platform_name} {sanitized_sender_nickname or sanitized_sender_name}: {chat_message.content_text}{ref_str}",
    )

    await message_service.push_human_message(
        message=chat_message,
        user=user,
        db_chat_channel=db_chat_channel,
        trigger_agent=trigger_agent,
    )
