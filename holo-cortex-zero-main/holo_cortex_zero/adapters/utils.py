"""适配器工具库

提供延迟加载的适配器相关工具方法，避免在业务逻辑中重复导入。
"""

from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    from holo_cortex_zero.adapters.interface.base import BaseAdapter

T = TypeVar("T", bound="BaseAdapter")


class AdapterUtils:
    """适配器工具类"""

    @staticmethod
    def get_adapter(adapter_key: str) -> "BaseAdapter":
        """获取适配器实例

        Args:
            adapter_key (str): 适配器标识

        Returns:
            BaseAdapter: 适配器实例
        """
        from holo_cortex_zero.adapters import get_adapter

        return get_adapter(adapter_key)

    @staticmethod
    def get_typed_adapter(adapter_key: str, adapter_type: type[T]) -> T:
        """获取指定类型的适配器实例

        Args:
            adapter_key (str): 适配器标识
            adapter_type (type[T]): 期望的适配器类型

        Returns:
            T: 指定类型的适配器实例
        """
        from holo_cortex_zero.adapters import get_adapter

        adapter = get_adapter(adapter_key)
        return cast(adapter_type, adapter)

    @staticmethod
    async def get_adapter_for_chat(chat_key: str) -> "BaseAdapter":
        """根据聊天标识获取适配器

        Args:
            chat_key (str): 聊天标识

        Returns:
            BaseAdapter: 适配器实例
        """
        from holo_cortex_zero.models.db_chat_channel import DBChatChannel

        db_chat_channel = await DBChatChannel.get_channel(chat_key=chat_key)
        return AdapterUtils.get_adapter(db_chat_channel.adapter_key)

# 创建全局实例，便于使用
adapter_utils = AdapterUtils()
