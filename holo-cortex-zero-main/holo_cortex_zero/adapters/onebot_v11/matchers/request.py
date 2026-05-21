from typing import Type

from nonebot import on_request
from nonebot.adapters.onebot.v11 import Bot, FriendRequestEvent, GroupRequestEvent, RequestEvent
from nonebot.matcher import Matcher

from holo_cortex_zero.core.logger import logger


request_matcher: Type[Matcher] = on_request(priority=99999, block=False)


@request_matcher.handle()
async def _(_: Matcher, event: RequestEvent, bot: Bot):
    from holo_cortex_zero.adapters.onebot_v11.adapter import OnebotV11Adapter
    from holo_cortex_zero.adapters.utils import adapter_utils

    adapter = adapter_utils.get_typed_adapter("onebot_v11", OnebotV11Adapter)

    if isinstance(event, FriendRequestEvent):
        if not adapter.config.AUTO_ACCEPT_PRIVATE_REQUEST:
            logger.info(f"OneBot 好友请求未自动接受: user_id={event.user_id} reason=private_request_disabled")
            return
        await bot.call_api("set_friend_add_request", flag=event.flag, approve=True)
        logger.info(f"OneBot 已自动接受好友请求: user_id={event.user_id}")
        return

    if isinstance(event, GroupRequestEvent):
        if not adapter.config.AUTO_ACCEPT_GROUP_REQUEST:
            logger.info(
                f"OneBot 群请求未自动接受: group_id={event.group_id} user_id={event.user_id} "
                "reason=group_request_disabled"
            )
            return
        await bot.call_api(
            "set_group_add_request",
            flag=event.flag,
            sub_type=event.sub_type,
            approve=True,
        )
        logger.info(f"OneBot 已自动接受群请求: group_id={event.group_id} user_id={event.user_id}")
        return

    logger.debug(f"OneBot 未处理请求事件: request_type={getattr(event, 'request_type', '')}")
