import hashlib
import json
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, Optional

from pydantic import BaseModel, Field, PrivateAttr

from holo_cortex_zero.core.config import CoreConfig, config
from holo_cortex_zero.core.runtime_identity import get_bot_persona_display_name

if TYPE_CHECKING:
    from nonebot.adapters.onebot.v11 import Bot as OneBotV11Bot

    from holo_cortex_zero.adapters.interface import BaseAdapter
    from holo_cortex_zero.models.db_chat_channel import DBChatChannel
    from holo_cortex_zero.models.db_user import DBUser


class WebhookRequest(BaseModel):
    """Webhook 请求模型，用于封装传入的 Webhook 数据。"""

    headers: Dict[str, str] = Field(..., description="Webhook 请求头")
    body: Dict[str, Any] = Field(..., description="Webhook 请求体")


class AgentCtx(BaseModel):
    _na_context_block_overrides: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _na_memory_recall_meta: Dict[str, Any] = PrivateAttr(default_factory=dict)
    """
    Agent 上下文（AgentCtx）

    `AgentCtx` 是 HoloCortexZero 中一个至关重要的概念，它封装了 Agent 在执行任务时所需的所有上下文信息。
    无论是在处理来自聊天软件的消息，还是响应一个 Webhook 事件，`AgentCtx` 都提供了统一的接口来访问相关数据和功能。

    扩展开发者可以通过 `AgentCtx` 对象安全地与 HoloCortexZero 的核心功能进行交互，
    例如读写文件、获取配置等，而无需关心底层的具体实现。

    在扩展实践中通常以 `_ctx` 作为变量名提供给运行时方法使用。
    """

    container_key: Optional[str] = Field(default=None, description="运行环境容器的唯一标识，用于隔离不同聊天频道的上下文。")
    from_chat_key: Optional[str] = Field(default=None, description="来源聊天的唯一标识，用于追溯消息来源。")
    webhook_request: Optional[WebhookRequest] = Field(
        default=None,
        description="当 Agent 由 Webhook 触发时，这里会包含 Webhook 的请求数据。",
    )
    channel_id: Optional[str] = Field(default=None, description="当前聊天频道的频道 ID，例如 QQ 群号或 用户 ID 等。")
    channel_name: Optional[str] = Field(default=None, description="当前聊天频道的频道名称，例如 QQ 群名或 用户名等。")
    channel_type: Optional[str] = Field(default=None, description="当前聊天频道的频道类型，例如 `group` 或 `private` 等。")
    adapter_key: Optional[str] = Field(default=None, description="当前聊天频道所使用的适配器标识，例如 `onebot_v11` 等。")
    _db_chat_channel: Optional["DBChatChannel"] = None  # 当前聊天频道的数据库聊天频道实例
    _trigger_db_user: Optional["DBUser"] = None  # 触发本次 Agent 的 DBUser 实例

    @property
    def chat_key(self) -> str:
        """
        聊天频道唯一ID。

        这是当前聊天频道的唯一标识符，通常由 `adapter_key` 和 `channel_id` 组成。

        Example:
            >>> _ctx.chat_key
            'onebot_v11-group_12345678'
        """
        if not self.from_chat_key:
            raise ValueError("missing from_chat_key")
        return self.from_chat_key

    @property
    def db_chat_channel(self) -> Optional["DBChatChannel"]:
        """
        当前聊天频道的数据库聊天频道实例。
        """
        return self._db_chat_channel

    @property
    def db_user(self) -> Optional["DBUser"]:
        """
        触发本次 Agent 的数据库用户实例。
        """
        return self._trigger_db_user

    @property
    def adapter(self) -> "BaseAdapter":
        """
        消息关联适配器实例。

        通过此适配器实例，扩展运行时可以获取适配器相关信息或调用适配器相关方法。
        """
        if not self.adapter_key:
            raise ValueError("missing adapter_key")
        from holo_cortex_zero.adapters.utils import adapter_utils

        return adapter_utils.get_adapter(self.adapter_key)

    @property
    def ms(self):
        """消息模块

        提供对底层 `holo_cortex_zero.api.message` 模块的直接访问。
        主要用于需要手动指定 `chat_key` 的高级场景，例如**向其他聊天频道发送消息**。

        当你需要向当前聊天频道以外的聊天频道发送通知或消息时，应使用此模块。
        便捷方法如 `_ctx.send_text()` 默认只能向当前聊天频道发送。

        Example:
            >>> # 假设运行时逻辑需要向一个监控频道发送状态更新
            >>> monitor_chat_key = "onebot_v11-group_987654321"
            >>>
            >>> # 使用 `_ctx.ms` 来向指定聊天频道发送消息
            >>> await _ctx.ms.send_text(monitor_chat_key, "System status: OK", _ctx)
            >>>
            >>> # 注意：调用底层模块时，需要手动传入 `_ctx` 对象。
        """
        from holo_cortex_zero.api import message

        return message

    async def get_core_config(self) -> CoreConfig:
        """
        获取当前生效的核心配置实例。

        核心配置由 `系统基本设定 -> 适配器设定 -> 聊天频道设定` 三层配置混合生成，
        聊天频道设定优先级最高。运行时逻辑可以通过此方法获取配置项。

        Example:
            >>> core_config = await ctx.get_core_config()
            >>> logger.info(core_config.ENSURE_SFW_CONTENT)
            True
        """
        if self._db_chat_channel is None:
            raise ValueError("未找到关联的数据库聊天频道")
        return config

    async def get_onebot_v11_bot(self) -> "OneBotV11Bot":
        """
        获取 OneBot V11 Bot 实例。

        注意：此方法仅适用于 OneBot V11 适配器！

        Example:
            >>> if ctx.adapter_key == "onebot_v11":
            ...     bot = await ctx.get_onebot_v11_bot()
            ...     await bot.send_private_msg(user_id=12345, message="Hello from HoloCortexZero!")
        """
        if self.adapter_key != "onebot_v11":
            raise ValueError("获取 OneBot V11 Bot 实例失败，当前适配器不是 OneBot V11")
        from holo_cortex_zero.adapters.onebot_v11.core.bot import get_bot

        return get_bot()

    async def send_text(self, content: str, *, record: bool = True):
        """发送文本消息到当前聊天频道。

        这是一个便捷方法，封装了 `message.send_text`，自动填充聊天频道信息。

        Args:
            content (str): 要发送的文本内容。
            record (bool): 是否将此消息记录到对话历史中，供 AI 后续参考。默认为 True。
                对于一些提示性、非关键性的消息，可以设置为 False，避免干扰 AI 的主线任务。

        Example:
            >>> await _ctx.send_text("Hello, this is a message from runtime.")
            >>> await _ctx.send_text("正在处理，请稍候...", record=False)
        """
        await self.ms.send_text(self.chat_key, content, self, record=record)

    async def send_image(self, file_path: str, *, record: bool = True):
        """发送图片到当前聊天频道。

        这是一个便捷方法，封装了 `message.send_image`，自动填充聊天频道信息。

        Args:
            file_path (str): 图片真实绝对路径。兼容旧虚拟路径，但不再推荐。
            record (bool): 是否将此消息记录到对话历史中。默认为 True。

        Example:
            >>> await _ctx.send_image("./output/result.png")
        """
        await self.ms.send_image(self.chat_key, file_path, self, record=record)

    async def send_file(self, file_path: str, *, record: bool = True):
        """发送文件到当前聊天频道。

        这是一个便捷方法，封装了 `message.send_file`，自动填充聊天频道信息。

        Args:
            file_path (str): 文件真实绝对路径。兼容旧虚拟路径，但不再推荐。
            record (bool): 是否将此消息记录到对话历史中。默认为 True。

        Example:
            >>> await _ctx.send_file("./output/report.txt")
        """
        await self.ms.send_file(self.chat_key, file_path, self, record=record)

    async def push_system(self, message: str, trigger_agent: bool = False):
        """推送系统消息

        这是一个便捷方法，封装了 `message.push_system`，自动填充聊天频道信息。

        Args:
            message (str): 要推送的系统消息内容。
            trigger_agent (bool): 是否触发 AI 响应。默认为 False。

        Example:
            >>> # 推送处理结果并触发 AI 响应
            >>> await _ctx.push_system_message("Search result of 'xxx' is: xxx. Please check the result.", trigger_agent=True)
        """
        await self.ms.push_system(self.chat_key, message, self, trigger_agent=trigger_agent)

    def _hash_context_block_text(self, text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]

    def _ensure_context_block_plan(self) -> Dict[str, Any]:
        plan = self._na_context_block_overrides
        if not isinstance(plan, dict) or not plan:
            plan = {
                "context_block_version": 2,
                "immutable_blocks": [],
                "persona_image_blocks": [],
                "short_memory_blocks": [],
                "stage2_blocks": [],
                "window_blocks": [],
                "window_image_blocks": [],
                "current_turn_blocks": [],
                "blocks": [],
            }
            self._na_context_block_overrides = plan
        return plan

    def _bucket_name_for_block_type(self, block_type: str) -> str:
        normalized = str(block_type or "").strip().lower()
        return {
            "immutable_text": "immutable_blocks",
            "persona_image": "persona_image_blocks",
            "short_memory": "short_memory_blocks",
            "stage2_delta": "stage2_blocks",
            "window_text": "window_blocks",
            "window_image": "window_image_blocks",
            "current_turn_text": "current_turn_blocks",
            "current_turn_image": "current_turn_blocks",
        }.get(normalized, "blocks")

    def add_context_block(
        self,
        *,
        block_type: str,
        text_payload: str = "",
        image_digest_refs: Optional[list[str]] = None,
        image_identity_refs: Optional[list[str]] = None,
        source_scope: str = "ctx",
        paired_text_ref: str = "",
        mutable: bool = True,
        order_key: Optional[int] = None,
        block_id: Optional[str] = None,
        section_kind: str = "",
        message_anchor: str = "",
        physical_order: Optional[int] = None,
    ) -> Dict[str, Any]:
        from holo_cortex_zero.services.agent.context_blocks import build_context_block

        plan = self._ensure_context_block_plan()
        bucket_name = self._bucket_name_for_block_type(block_type)
        bucket = plan.setdefault(bucket_name, [])
        text_payload = str(text_payload or "")
        image_digest_refs = [str(item) for item in (image_digest_refs or []) if str(item or "")]
        image_identity_refs = [str(item) for item in (image_identity_refs or []) if str(item or "")]
        order = len(bucket) if order_key is None else int(order_key)
        resolved_block_id = str(block_id or f"{source_scope}:{block_type}:{order}:{self._hash_context_block_text(text_payload or paired_text_ref)}")
        block = build_context_block(
            block_id=resolved_block_id,
            block_type=str(block_type),
            order_key=order,
            source_scope=source_scope,
            text_payload=text_payload,
            image_digest_refs=image_digest_refs,
            image_identity_refs=image_identity_refs,
            paired_text_ref=paired_text_ref,
            mutable=bool(mutable),
            section_kind=section_kind,
            message_anchor=message_anchor,
            physical_order=physical_order,
        )
        bucket.append(block)
        plan.setdefault("blocks", []).append(block)
        return block

    def merge_context_block_plan(self, plan: Dict[str, Any]) -> None:
        if not isinstance(plan, dict):
            return
        current = self._ensure_context_block_plan()
        for key in (
            "immutable_blocks",
            "persona_image_blocks",
            "short_memory_blocks",
            "stage2_blocks",
            "window_blocks",
            "window_image_blocks",
            "current_turn_blocks",
            "blocks",
        ):
            value = plan.get(key)
            if isinstance(value, list):
                current.setdefault(key, []).extend(dict(item) for item in value if isinstance(item, dict))
        for key in ("context_block_version", "upstream_window_size", "upstream_window_message_count", "upstream_window_image_count", "upstream_vision_image_limit"):
            if key in plan:
                current[key] = plan.get(key)

    def get_context_block_plan(self) -> Dict[str, Any]:
        return dict(self._ensure_context_block_plan())

    async def get_persona_display_name(self) -> str:
        """获取当前系统唯一主人格显示名。"""
        from holo_cortex_zero.models.db_chat_channel import DBChatChannel

        if self.chat_key and not self._db_chat_channel:
            self._db_chat_channel = await DBChatChannel.get_channel(chat_key=self.chat_key)
        if self._db_chat_channel:
            return self._db_chat_channel.get_persona_display_name()
        return get_bot_persona_display_name(config)

    async def current_persona_name(self) -> str:
        """当前主人格显示名的兼容别名。"""
        return await self.get_persona_display_name()

    @classmethod
    def create_by_db_chat_channel(
        cls,
        db_chat_channel: "DBChatChannel",
        container_key: Optional[str] = None,
        from_chat_key: Optional[str] = None,
        webhook_request: Optional[WebhookRequest] = None,
    ) -> "AgentCtx":
        """从数据库聊天频道创建 AgentCtx (内部方法)"""
        return cls(
            container_key=container_key,
            from_chat_key=from_chat_key or db_chat_channel.chat_key,
            channel_id=db_chat_channel.channel_id,
            channel_name=db_chat_channel.channel_name,
            channel_type=db_chat_channel.channel_type,
            adapter_key=db_chat_channel.adapter_key,
            webhook_request=webhook_request,
            _db_chat_channel=db_chat_channel,
        )

    @classmethod
    async def create_by_chat_key(
        cls,
        chat_key: str,
        container_key: Optional[str] = None,
        from_chat_key: Optional[str] = None,
        webhook_request: Optional[WebhookRequest] = None,
    ) -> "AgentCtx":
        """从聊天频道创建 AgentCtx (内部方法)"""
        from holo_cortex_zero.models.db_chat_channel import DBChatChannel

        db_chat_channel = await DBChatChannel.get_channel(chat_key=chat_key)
        return cls.create_by_db_chat_channel(db_chat_channel, container_key, from_chat_key, webhook_request)

    @classmethod
    async def create_by_webhook(
        cls,
        webhook_request: WebhookRequest,
    ) -> "AgentCtx":
        """从 Webhook 请求创建 AgentCtx (内部方法)"""
        return cls(webhook_request=webhook_request)
