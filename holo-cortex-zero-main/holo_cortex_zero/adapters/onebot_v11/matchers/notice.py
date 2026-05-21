import time
from typing import Any, Dict, Optional, Type

from nonebot import on_notice
from nonebot.adapters.onebot.v11 import Bot, NoticeEvent
from nonebot.matcher import Matcher

from holo_cortex_zero.adapters.onebot_v11.tools.onebot_util import get_user_name
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.models.db_user import DBUser
from holo_cortex_zero.schemas.chat_message import ChatMessage, ChatType
from holo_cortex_zero.services.message_service import message_service
from holo_cortex_zero.services.notice_service import (
    BaseNoticeHandler,
    NoticeConfig,
    NoticeResult,
)
from holo_cortex_zero.tools.time_util import format_duration


class PokeNoticeHandler(BaseNoticeHandler):
    """戳一戳通知处理器"""

    def match(self, event_dict: Dict[str, Any]) -> Optional[Dict[str, str]]:
        if event_dict.get("notice_type") != "notify" or event_dict.get("sub_type") != "poke":
            return None
        raw_info = event_dict.get("raw_info", [])
        poke_style = raw_info[2].get("txt", "戳一戳") if len(raw_info) > 2 else "戳一戳"
        poke_style_suffix = raw_info[4].get("txt", "") if len(raw_info) > 4 else ""
        return {
            "user_id": str(event_dict["user_id"]),
            "target_id": str(event_dict["target_id"]),
            "poke_style": poke_style,
            "poke_style_suffix": poke_style_suffix,
        }

    async def format_message(self, _db_chat_channel: DBChatChannel, info: Dict[str, str]) -> str:
        from holo_cortex_zero.adapters.onebot_v11.adapter import OnebotV11Adapter

        adapter = _db_chat_channel.adapter.cast(OnebotV11Adapter)
        if str(info["target_id"]) == str(adapter.config.BOT_QQ):
            return f"( {info['poke_style']} {_db_chat_channel.get_persona_display_name()} {info['poke_style_suffix']})"
        return f"({info['poke_style']} {info['target_id']} {info['poke_style_suffix']})"


class GroupIncreaseNoticeHandler(BaseNoticeHandler):
    """群成员增加通知处理器"""

    def get_notice_config(self) -> NoticeConfig:
        return NoticeConfig(force_tome=True, use_system_sender=True)

    def match(self, event_dict: Dict[str, Any]) -> Optional[Dict[str, str]]:
        if event_dict.get("notice_type") != "group_increase":
            return None
        return {
            "user_id": str(event_dict["user_id"]),
        }

    async def format_message(self, _db_chat_channel: DBChatChannel, info: Dict[str, str]) -> str:
        return f"(新成员 (qq:{info['user_id']}) 加入群聊)"


class GroupDecreaseNoticeHandler(BaseNoticeHandler):
    """群成员减少通知处理器"""

    def get_notice_config(self) -> NoticeConfig:
        return NoticeConfig(force_tome=True, use_system_sender=True)

    def match(self, event_dict: Dict[str, Any]) -> Optional[Dict[str, str]]:
        if event_dict.get("notice_type") != "group_decrease":
            return None
        return {
            "user_id": str(event_dict["user_id"]),
        }

    async def format_message(self, _db_chat_channel: DBChatChannel, info: Dict[str, str]) -> str:
        return f"(成员 (qq:{info['user_id']}) 退出群聊)"


class GroupBanNoticeHandler(BaseNoticeHandler):
    """群禁言通知处理器"""

    def get_notice_config(self) -> NoticeConfig:
        return NoticeConfig(force_tome=False, use_operator_as_sender=True)

    def match(self, event_dict: Dict[str, Any]) -> Optional[Dict[str, str]]:
        if event_dict.get("notice_type") != "group_ban":
            return None
        return {
            "user_id": str(event_dict["user_id"]),
            "operator_id": str(event_dict["operator_id"]),
            "duration": str(event_dict["duration"]),
        }

    async def format_message(self, _db_chat_channel: DBChatChannel, info: Dict[str, str]) -> str:
        duration = int(info["duration"])
        if duration == 0:
            return f"(成员 (qq:{info['user_id']}) 被管理员 (qq:{info['operator_id']}) 解除禁言)"
        duration_str = format_duration(duration)
        return f"(成员 (qq:{info['user_id']}) 被管理员 (qq:{info['operator_id']}) 禁言 {duration_str})"


class GroupRecallNoticeHandler(BaseNoticeHandler):
    """群消息撤回通知处理器"""

    def get_notice_config(self) -> NoticeConfig:
        return NoticeConfig(force_tome=False, use_system_sender=True)

    def match(self, event_dict: Dict[str, Any]) -> Optional[Dict[str, str]]:
        if event_dict.get("notice_type") != "group_recall":
            return None
        return {
            "user_id": str(event_dict["user_id"]),
            "operator_id": str(event_dict["operator_id"]),
            "message_id": str(event_dict["message_id"]),
        }

    async def format_message(self, _db_chat_channel: DBChatChannel, info: Dict[str, str]) -> str:
        # 如果是自己撤回
        if info["user_id"] == info["operator_id"]:
            return f"(成员 (qq:{info['user_id']}) 撤回了一条消息，但该消息仍然对你可见)"
        # 如果是被管理员撤回
        return f"(成员 (qq:{info['user_id']}) 的一条消息被管理员 (qq:{info['operator_id']}) 撤回，但该消息仍然对你可见)"


class GroupAdminNoticeHandler(BaseNoticeHandler):
    """群管理员变动通知处理器"""

    def get_notice_config(self) -> NoticeConfig:
        return NoticeConfig(force_tome=True, use_system_sender=True)

    def match(self, event_dict: Dict[str, Any]) -> Optional[Dict[str, str]]:
        if event_dict.get("notice_type") != "group_admin":
            return None
        return {
            "user_id": str(event_dict["user_id"]),
            "group_id": str(event_dict["group_id"]),
            "action": event_dict["sub_type"],  # set/unset
        }

    async def format_message(self, _db_chat_channel: DBChatChannel, info: Dict[str, str]) -> str:
        action_map = {
            "set": "被设置为管理员",
            "unset": "被取消管理员身份",
        }
        return f"(成员 (qq:{info['user_id']}) {action_map[info['action']]})"


class NoticeHandlerManager:
    """通知处理器管理器"""

    def __init__(self):
        self._handlers: list[BaseNoticeHandler] = []

    def register(self, handler: BaseNoticeHandler):
        """注册处理器"""
        self._handlers.append(handler)

    async def handle(self, event_dict: Dict[str, Any]) -> Optional[NoticeResult]:
        """处理通知事件

        Args:
            event_dict (Dict[str, Any]): 通知事件字典

        Returns:
            Optional[NoticeResult]: 处理结果，包含处理器实例和通知信息
        """
        for handler in self._handlers:
            if info := handler.match(event_dict):
                return NoticeResult(
                    handler=handler,
                    info=info,
                )
        return None


# 全局通知处理器管理器
notice_manager = NoticeHandlerManager()
# 注册所有通知处理器
notice_manager.register(GroupAdminNoticeHandler())
notice_manager.register(PokeNoticeHandler())
notice_manager.register(GroupIncreaseNoticeHandler())
notice_manager.register(GroupDecreaseNoticeHandler())
notice_manager.register(GroupBanNoticeHandler())
notice_manager.register(GroupRecallNoticeHandler())


"""通用通知匹配器"""
notice_matcher: Type[Matcher] = on_notice(priority=99999, block=False)


def _positive_id(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if int(raw) <= 0:
            return None
    except ValueError:
        return None
    return raw


def _resolve_notice_chat_info(
    event_dict: Dict[str, Any],
    handler: BaseNoticeHandler,
) -> Optional[tuple[str, ChatType]]:
    """把已匹配的业务通知投递到真实会话。

    主干：notice 只有在能解析出真实 OneBot 会话时才进入频道/上下文链路。
    分支兼容：NapCat 会把 input_status 这类非会话通知上报为 group_id=0，不能伪造成 group_0。
    """
    group_id = _positive_id(event_dict.get("group_id"))
    if group_id:
        return f"onebot_v11-group_{group_id}", ChatType.GROUP

    if isinstance(handler, PokeNoticeHandler):
        user_id = _positive_id(event_dict.get("user_id"))
        if user_id:
            return f"onebot_v11-private_{user_id}", ChatType.PRIVATE

    return None


@notice_matcher.handle()
async def _(_: Matcher, event: NoticeEvent, bot: Bot):
    from holo_cortex_zero.adapters.onebot_v11.adapter import OnebotV11Adapter

    event_dict = dict(event)
    result = await notice_manager.handle(event_dict)
    if not result:
        logger.debug(
            f"收到未处理的通知类型: {event_dict}\n"
            f"notice_type: {event_dict.get('notice_type')}\n"
            f"sub_type: {event_dict.get('sub_type')}\n",
        )
        return

    handler = result["handler"]
    info = result["info"]
    resolved_chat = _resolve_notice_chat_info(event_dict, handler)
    if not resolved_chat:
        logger.warning(
            "OneBot 通知缺少可投递会话，已跳过: "
            f"notice_type={event_dict.get('notice_type')} sub_type={event_dict.get('sub_type')} "
            f"group_id={event_dict.get('group_id')} user_id={event_dict.get('user_id')}"
        )
        return

    chat_key, chat_type = resolved_chat
    db_chat_channel: Optional[DBChatChannel] = await DBChatChannel.get_or_none(chat_key=chat_key)
    if not db_chat_channel:
        logger.warning(
            "OneBot 通知目标频道未注册，已跳过: "
            f"chat_key={chat_key} notice_type={event_dict.get('notice_type')} sub_type={event_dict.get('sub_type')}"
        )
        return

    adapter: OnebotV11Adapter = db_chat_channel.adapter.cast(OnebotV11Adapter)

    # 格式化消息
    content_text = await handler.format_message(db_chat_channel, info)

    if handler.config.use_system_sender:
        # 使用系统消息
        await message_service.push_system_message(
            chat_key=chat_key,
            agent_messages=content_text,
            trigger_agent=handler.config.force_tome,
            db_chat_channel=db_chat_channel,
        )
    else:
        # 使用普通消息
        platform_userid: str = handler.get_sender_platform_userid(info)
        user: Optional[DBUser] = await DBUser.get_or_none(
            adapter_key=db_chat_channel.adapter_key,
            platform_userid=platform_userid,
        )
        if chat_type == ChatType.GROUP:
            sender_nickname = await get_user_name(event=event, bot=bot, user_id=platform_userid, db_chat_channel=db_chat_channel)
        else:
            sender_nickname = user.username if user else platform_userid

        if user and not user.is_active:
            logger.info(f"用户 {platform_userid} 被封禁，封禁结束时间: {user.ban_until}")
            return

        chat_message: ChatMessage = ChatMessage(
            message_id="",
            sender_id=str(user.id) if user else platform_userid,
            sender_name=user.username if user else sender_nickname,
            sender_nickname=sender_nickname,
            adapter_key=db_chat_channel.adapter_key,
            platform_userid=platform_userid,
            is_tome=(
                1
                if (
                    handler.config.force_tome
                    or (isinstance(handler, PokeNoticeHandler) and info["target_id"] == adapter.config.BOT_QQ)
                )
                else 0
            ),
            is_recalled=False,
            chat_key=chat_key,
            chat_type=chat_type,
            content_text=content_text,
            content_data=[],
            ext_data={},
            send_timestamp=int(time.time()),
        )
        await message_service.push_human_message(message=chat_message, user=user)
