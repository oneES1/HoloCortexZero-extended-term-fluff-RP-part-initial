import json
from typing import Any, Optional, Tuple, Union, cast

from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import (
    GroupIncreaseNoticeEvent,
    GroupMessageEvent,
    GroupUploadNoticeEvent,
    MessageEvent,
    NoticeEvent,
)

from holo_cortex_zero.adapters.onebot_v11.core.bot import get_bot
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.schemas.chat_message import ChatType
from holo_cortex_zero.tools.common_util import limited_text_output


def _get_runtime_cache_bucket(runtime_cache: Optional[dict[str, Any]], bucket_name: str) -> Optional[dict[Any, Any]]:
    if runtime_cache is None:
        return None
    bucket = runtime_cache.get(bucket_name)
    if isinstance(bucket, dict):
        return bucket
    bucket = {}
    runtime_cache[bucket_name] = bucket
    return bucket


async def _get_group_member_info_cached(
    *,
    bot: Bot,
    group_id: Union[int, str],
    user_id: Union[int, str],
    runtime_cache: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    cache_bucket = _get_runtime_cache_bucket(runtime_cache, "group_member_info")
    cache_key = (int(group_id), int(user_id))
    if cache_bucket is not None and cache_key in cache_bucket:
        logger.debug(f"OneBot 群成员信息命中单消息缓存: group_id={group_id} user_id={user_id}")
        return cache_bucket[cache_key]

    user_info = await bot.get_group_member_info(
        group_id=group_id,
        user_id=user_id,
        no_cache=False,
    )
    if cache_bucket is not None:
        cache_bucket[cache_key] = user_info
        logger.debug(f"OneBot 群成员信息写入单消息缓存: group_id={group_id} user_id={user_id}")
    return user_info


async def gen_chat_text(
    event: MessageEvent,
    bot: Bot,
    db_chat_channel: DBChatChannel,
    runtime_cache: Optional[dict[str, Any]] = None,
) -> Tuple[str, int]:
    """生成合适的聊天消息内容(eg. 将cq at 解析为真实的名字)

    Args:
        event (MessageEvent): 事件对象
        bot (Bot): 机器人对象

    Returns:
        Tuple[str, int]: 聊天消息内容, 是否与自身相关
    """
    if not isinstance(event, GroupMessageEvent):
        return event.get_plaintext(), 0

    is_tome: int = 0
    msg = ""
    for seg in event.message:
        if seg.is_text():
            msg += seg.data.get("text", "")
        elif seg.type == "at":
            qq = seg.data.get("qq", None)
            if qq:
                if qq == "all":
                    msg += "[@id:all;nickname:全体成员@]"
                    is_tome = 1
                else:
                    user_name = await get_user_name(
                        event=event,
                        bot=bot,
                        user_id=int(qq),
                        db_chat_channel=db_chat_channel,
                        runtime_cache=runtime_cache,
                    )
                    if user_name:
                        msg += f"[@id:{qq};nickname:{user_name}@]"  # 保持给bot看到的内容与真实用户看到的一致
        elif seg.type == "json":
            # 处理JSON卡片消息（延迟导入避免循环依赖）
            try:
                from holo_cortex_zero.adapters.onebot_v11.tools.convertor import (
                    JSON_CARD_FALLBACK_TEXT,
                    parse_onebot_json_segment,
                )

                text_summary, _, _ = parse_onebot_json_segment(seg.data)
                msg += text_summary
            except json.JSONDecodeError as e:
                logger.warning(f"JSON卡片解析失败（格式错误）: {e}")
                from holo_cortex_zero.adapters.onebot_v11.tools.convertor import (
                    JSON_CARD_FALLBACK_TEXT,
                )
                msg += JSON_CARD_FALLBACK_TEXT
            except Exception as e:
                logger.error(f"处理JSON卡片时发生意外错误: {e}", exc_info=True)
                from holo_cortex_zero.adapters.onebot_v11.tools.convertor import (
                    JSON_CARD_FALLBACK_TEXT,
                )
                msg += JSON_CARD_FALLBACK_TEXT
    return msg, is_tome


async def get_user_name(
    event: Union[MessageEvent, GroupIncreaseNoticeEvent, GroupUploadNoticeEvent, NoticeEvent],
    bot: Bot,
    user_id: Union[int, str],
    db_chat_channel: DBChatChannel,
    runtime_cache: Optional[dict[str, Any]] = None,
) -> str:
    """获取QQ用户名"""
    if str(user_id) == (await db_chat_channel.adapter.get_self_info()).user_id:
        return db_chat_channel.get_persona_display_name()

    if isinstance(event, GroupMessageEvent) and event.sub_type == "anonymous" and event.anonymous:  # 匿名消息
        return f"[匿名]{event.anonymous.name}"

    if isinstance(event, GroupMessageEvent) and str(event.user_id) == str(user_id):
        direct_name = event.sender.card or event.sender.nickname
        if direct_name:
            logger.debug(f"OneBot 用户名直接使用事件载荷: group_id={event.group_id} user_id={user_id}")
            return direct_name

    if isinstance(event, (GroupMessageEvent, GroupIncreaseNoticeEvent, NoticeEvent)):
        group_id = getattr(event, "group_id", None)
        if group_id:
            user_info = await _get_group_member_info_cached(
                bot=bot,
                group_id=group_id,
                user_id=user_id,
                runtime_cache=runtime_cache,
            )
        else:
            raise ValueError("获取群成员信息失败")
        user_name = user_info.get("nickname", None)
        user_name = user_info.get("card", None) or user_name
    else:
        user_name = (
            event.sender.nickname if not isinstance(event, GroupUploadNoticeEvent) and event.sender else event.get_user_id()
        )

    if not user_name:
        raise ValueError("获取用户名失败")

    return user_name


async def get_user_group_card_name(
    group_id: Union[int, str],
    user_id: Union[int, str],
    db_chat_channel: DBChatChannel,
    runtime_cache: Optional[dict[str, Any]] = None,
) -> str:
    """获取用户所在群的群名片"""
    if str(user_id) == (await db_chat_channel.adapter.get_self_info()).user_id:
        return db_chat_channel.get_persona_display_name()
    if str(user_id) == "all" or str(user_id) == "0":
        return "全体成员"
    user_info = await _get_group_member_info_cached(
        bot=get_bot(),
        group_id=int(group_id),
        user_id=int(user_id),
        runtime_cache=runtime_cache,
    )
    return user_info.get("card") or user_info.get("nickname", "未知")


async def get_chat_info(
    event: Union[MessageEvent, GroupUploadNoticeEvent],
) -> Tuple[str, ChatType]:
    """获取频道信息"""
    if isinstance(event, GroupUploadNoticeEvent):
        raw_chat_type = "group"
    else:
        raw_chat_type = event.message_type
    chat_type: ChatType
    if raw_chat_type == "friend" or raw_chat_type == "private":
        event = cast(MessageEvent, event)
        channel_id: str = f"private_{event.user_id}"
        chat_type = ChatType.PRIVATE
    elif raw_chat_type == "group":
        event = cast(GroupMessageEvent, event)
        channel_id = f"group_{event.group_id}"
        chat_type = ChatType.GROUP  # noqa: F841
    else:
        chat_type = ChatType.UNKNOWN
        raise ValueError("未知的消息类型")

    return channel_id, chat_type


async def get_chat_info_old(
    event: MessageEvent,
) -> Tuple[str, ChatType]:
    """获取消息频道信息(旧版)

    直接返回完整频道标识适配旧功能需求
    """
    raw_chat_type = event.message_type
    chat_type: ChatType
    if raw_chat_type == "friend" or raw_chat_type == "private":
        event = cast(MessageEvent, event)
        channel_id: str = f"private_{event.user_id}"
        chat_type = ChatType.PRIVATE
    elif raw_chat_type == "group":
        event = cast(GroupMessageEvent, event)
        channel_id = f"group_{event.group_id}"
        chat_type = ChatType.GROUP  # noqa: F841
    else:
        chat_type = ChatType.UNKNOWN
        raise ValueError("未知的消息类型")

    if str(channel_id) == "0":
        raise ValueError(f"接收到频道ID为 0 的消息，源消息数据 -> {limited_text_output(event.model_dump_json(), 1024)}")

    return f"onebot_v11-{channel_id}", chat_type


async def get_message_reply_info(event: MessageEvent) -> str:
    """获取消息回复信息"""
    if not event.original_message:
        return ""
    for seg in event.original_message:
        if seg.type == "reply":
            return str(seg.data.get("id") or "")
    return ""
