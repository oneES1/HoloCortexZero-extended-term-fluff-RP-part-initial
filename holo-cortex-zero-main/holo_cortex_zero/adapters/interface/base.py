from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Generic, List, Tuple, Type, TypeVar, cast

from fastapi import APIRouter
from nonebot import logger
from pydantic import BaseModel

from holo_cortex_zero.core.core_utils import ConfigBase
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.core.runtime_identity import get_primary_advanced_user_id
from holo_cortex_zero.schemas.chat_message import ChatType

from .schemas.platform import (
    PlatformChannel,
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformUser,
)


class AdapterMetadata(BaseModel):
    """适配器元数据"""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    homepage: str = ""
    tags: List[str] = []


class BaseAdapterConfig(ConfigBase):
    """适配器配置基类"""


# 定义配置类型变量，约束为 BaseAdapterConfig 子类
TConfig = TypeVar("TConfig", bound=BaseAdapterConfig)
T = TypeVar("T", bound="BaseAdapter")


class BaseAdapter(ABC, Generic[TConfig]):
    """适配器基类"""

    _router: APIRouter  # 实例变量的类型注解
    _Configs: Type[TConfig]
    _config: TConfig

    def __init__(self, config_cls: Type[TConfig] = BaseAdapterConfig):
        self._Configs = config_cls
        self._adapter_config_path = Path(OsEnv.DATA_DIR) / "configs" / self.key / "config.yaml"
        self._config = self.get_config(self._Configs)

        # 注册配置到统一配置系统
        from holo_cortex_zero.core.core_utils import ConfigManager

        ConfigManager.register_config(f"adapter_{self.key}", self._config)

    @property
    @abstractmethod
    def key(self) -> str:
        """适配器唯一标识"""
        raise NotImplementedError

    @property
    @abstractmethod
    def metadata(self) -> AdapterMetadata:
        """适配器元数据"""
        raise NotImplementedError

    def get_adapter_router(self) -> APIRouter:
        """获取适配器路由"""
        return APIRouter()

    @property
    def router(self) -> APIRouter:
        """获取适配器路由"""
        if hasattr(self, "_router"):
            return self._router
        self._router = self.get_adapter_router()
        return self._router

    def get_config(self, config_cls: Type[TConfig]) -> TConfig:
        """获取适配器配置"""
        if not hasattr(self, "_config"):
            self._config = self._Configs.load_config(file_path=self._adapter_config_path)
            self._config.dump_config(self._adapter_config_path)
        return cast(config_cls, self._config)

    @property
    def config(self) -> TConfig:
        """获取适配器配置"""
        return self.get_config(self._Configs)

    @property
    def config_path(self) -> Path:
        """获取适配器配置路径"""
        return self._adapter_config_path

    def cast(self, adapter_type: Type[T]) -> T:
        """转换适配器类型"""
        return cast(adapter_type, self)

    @property
    def chat_key_rules(self) -> List[str]:
        return [
            "Group chat: `platform-group_123456` (where 123456 is the group number)",
            "Private chat: `platform-private_123456` (where 123456 is the user's QQ number)",
        ]

    @property
    def init_in_background(self) -> bool:
        """Whether adapter init should avoid blocking the backend startup path."""
        return False

    def get_primary_advanced_platform_user_ids(self) -> set[str]:
        """Return platform-side ids belonging to the primary HCZ advanced user.

        Mainline: adapters identify platform users only. The HCZ canonical
        advanced id is always resolved from core config by the shared identity
        mapper, so changing ADVANCED_USER_ID does not require adapter rewrites.
        The base class intentionally does not guess that any protocol id equals
        the HCZ advanced id; each adapter must expose its configured owner id.
        """
        return set()

    def is_primary_advanced_platform_user(self, user_id: str) -> bool:
        normalized = str(user_id or "").strip()
        return bool(normalized and normalized in self.get_primary_advanced_platform_user_ids())

    def canonical_private_channel_id(self) -> str:
        return f"private_{get_primary_advanced_user_id()}"

    @abstractmethod
    async def init(self) -> None:
        """初始化适配器"""
        raise NotImplementedError

    @abstractmethod
    async def cleanup(self) -> None:
        """清理适配器"""
        raise NotImplementedError

    @abstractmethod
    async def forward_message(self, request: PlatformSendRequest) -> PlatformSendResponse:
        """推送消息到协议端

        Args:
            request: 协议端发送请求，包含已经预处理好的消息数据

        Returns:
            PlatformSendResponse: 发送结果
        """
        raise NotImplementedError

    @abstractmethod
    async def get_self_info(self) -> PlatformUser:
        """获取自身信息"""
        raise NotImplementedError

    @abstractmethod
    async def get_user_info(self, user_id: str, channel_id: str) -> PlatformUser:
        """获取用户(或者群聊用户)信息"""
        raise NotImplementedError

    @abstractmethod
    async def get_channel_info(self, channel_id: str) -> PlatformChannel:
        """获取频道信息"""
        raise NotImplementedError

    async def set_message_reaction(self, message_id: str, status: bool = True) -> bool:  # noqa: ARG002
        """设置消息反应（可选实现）

        Args:
            message_id (str): 消息ID
            status (bool): True为设置反应，False为取消反应

        Returns:
            bool: 是否成功设置
        """
        # 默认实现：不支持消息反应功能
        return False

    async def edit_message(self, chat_key: str, message_id: str, text: str) -> PlatformSendResponse:  # noqa: ARG002
        """编辑已发送消息（可选实现）"""
        return PlatformSendResponse(success=False, error_message="adapter does not support edit_message")

    async def delete_message(self, chat_key: str, message_id: str) -> bool:  # noqa: ARG002
        """删除已发送消息（可选实现）"""
        return False

    # region 辅助方法

    def build_chat_key(self, channel_id: str) -> str:
        """构建聊天标识"""
        return f"{self.key}-{channel_id}"

    def parse_chat_key(self, chat_key: str) -> Tuple[str, str]:
        """解析聊天标识

        Args:
            chat_key: 聊天标识

        Returns:
            Tuple[str, str]: (adapter_key, channel_id)
        """
        parts = chat_key.split("-", 1)

        if len(parts) != 2:
            raise ValueError(f"无效的聊天标识: {chat_key}")

        adapter_key = parts[0]
        channel_id = parts[1]

        return adapter_key, channel_id

    # endregion
