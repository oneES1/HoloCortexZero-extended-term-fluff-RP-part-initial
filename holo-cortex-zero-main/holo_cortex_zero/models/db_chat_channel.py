from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model

from holo_cortex_zero.adapters.utils import adapter_utils
from holo_cortex_zero.core import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.runtime_identity import get_bot_persona_display_name, get_primary_advanced_user_id
from holo_cortex_zero.schemas.chat_message import ChatType

if TYPE_CHECKING:
    from holo_cortex_zero.adapters.interface.base import BaseAdapter


class DBChatChannel(Model):
    """数据库聊天频道模型"""

    id = fields.IntField(pk=True, generated=True, description="ID")
    is_active = fields.BooleanField(default=True, description="是否激活")
    data = fields.TextField(default="{}", description="频道数据")

    adapter_key = fields.CharField(max_length=64, index=True, description="适配器标识")
    channel_id = fields.CharField(max_length=64, index=True, description="频道 ID")
    channel_name = fields.CharField(max_length=64, null=True, description="频道名称")
    channel_type = fields.CharField(max_length=32, null=True, description="频道类型")

    chat_key = fields.CharField(max_length=64, index=True, description="全局聊天频道唯一标识")
    conversation_start_time = fields.DatetimeField(auto_now_add=True, description="对话起始时间")

    create_time = fields.DatetimeField(auto_now_add=True, description="创建时间")
    update_time = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:  # type: ignore
        table = "chat_channel"

    @classmethod
    def _default_active_for_new_channel(cls, channel_id: str, channel_type: ChatType) -> bool:
        if channel_type == ChatType.PRIVATE and str(channel_id or "").strip() == f"private_{get_primary_advanced_user_id(config)}":
            return True
        if channel_type == ChatType.GROUP:
            return bool(config.SESSION_GROUP_ACTIVE_DEFAULT)
        if channel_type == ChatType.PRIVATE:
            return bool(config.SESSION_PRIVATE_ACTIVE_DEFAULT)
        return False

    @classmethod
    async def get_or_create(
        cls,
        adapter_key: str,
        channel_id: str,
        channel_type: ChatType,
        channel_name: str = "",
    ) -> "DBChatChannel":
        """获取或创建聊天频道"""
        channel = await cls.get_or_none(adapter_key=adapter_key, channel_id=channel_id)
        if not channel:
            is_active = cls._default_active_for_new_channel(channel_id=channel_id, channel_type=channel_type)
            logger.info(
                "新聊天频道默认激活状态: adapter=%s channel=%s type=%s is_active=%s",
                adapter_key,
                channel_id,
                channel_type.value,
                is_active,
            )
            channel = await cls.create(
                adapter_key=adapter_key,
                channel_id=channel_id,
                channel_type=channel_type.value,
                channel_name=channel_name,
                chat_key=f"{adapter_key}-{channel_id}",
                is_active=is_active,
            )
        else:
            if channel_name and channel.channel_name != channel_name:
                logger.info(f"更新频道名称: {channel.channel_name} -> {channel_name}")
                channel.channel_name = channel_name
                await channel.save()
            if channel_type and channel.channel_type != channel_type.value:
                logger.info(f"更新频道类型: {channel.channel_type} -> {channel_type.value}")
                channel.channel_type = channel_type.value
                await channel.save()
        return channel

    @classmethod
    async def get_channel(cls, chat_key: str) -> "DBChatChannel":
        """获取聊天频道"""
        assert chat_key, "获取聊天频道失败，chat_key 为空"
        channel = await cls.get_or_none(chat_key=chat_key)
        if not channel:
            raise ValueError(f"聊天频道不存在: {chat_key}")
        return channel

    async def set_active(self, is_active: bool):
        """设置频道是否激活"""
        self.is_active = is_active
        await self.save()

    @property
    def chat_type(self) -> ChatType:
        """获取聊天频道类型"""
        try:
            return ChatType(self.channel_type)
        except ValueError as e:
            logger.error(f"获取聊天频道类型失败: {e!s}")
            return ChatType.UNKNOWN

    @property
    def adapter(self) -> "BaseAdapter":
        """获取适配器"""
        return adapter_utils.get_adapter(self.adapter_key)

    @staticmethod
    def get_persona_display_name() -> str:
        return get_bot_persona_display_name(config)
