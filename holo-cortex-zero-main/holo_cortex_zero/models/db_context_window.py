"""上下文窗口数据库模型

对话窗口 (Dialog Window) = 物理通道：QQ私聊/QQ群/TG私聊
上下文窗口 (Context Window) = AI 看到的逻辑上下文：
  - 高级用户: context_id = 配置的高级 user_id
  - 普通用户: context_id = chat_key (等同对话窗口)
"""
from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class DBContextWindow(Model):
    """上下文窗口持久化模型"""

    # 重要：DBContextWindow 是 context 路由、timeline、auto_memory、tool 链共同写入的共享状态行。
    # 禁止在业务代码中裸 `await window.save()`；旧 ORM 对象会把未负责的旧字段一起写回，
    # 例如 timeline 只改 summary_generating，却覆盖 auto_memory_pending_count。
    # 主干规则：谁改哪个字段，就用 save(update_fields=[...]) 只保存这些字段。

    id = fields.IntField(pk=True, generated=True, description="自增 ID")

    # 核心标识
    context_id = fields.CharField(
        max_length=128, unique=True, index=True,
        description="上下文窗口唯一标识：高级用户=user_id, 普通用户=chat_key",
    )
    owner_type = fields.CharField(
        max_length=16, default="normal",
        description="窗口类型: advanced | normal",
    )
    active_dialog_id = fields.CharField(
        max_length=128, default="",
        description="当前锚定的对话窗口 chat_key",
    )

    # 高级 context 模式状态；普通 context 不读取、不应用
    advanced_context_mode = fields.CharField(
        max_length=32,
        default="norm",
        description="高级 context 当前模式: norm | deek | deep",
    )
    advanced_context_mode_source = fields.CharField(
        max_length=32,
        default="default",
        description="高级 context 模式来源: default | manual",
    )

    # timeline 压缩状态
    compressed_summary = fields.TextField(default="", description="当前压缩摘要文本")
    last_compress_version = fields.IntField(default=0, description="最后一次压缩版本号")
    msg_count_since_compress = fields.IntField(default=0, description="距上次压缩的消息计数")
    summary_generating = fields.BooleanField(default=False, description="正在异步生成新摘要")
    pending_summary = fields.TextField(default="", null=True, description="生成完成但未应用的新摘要")
    pending_summary_ready = fields.BooleanField(default=False, description="新摘要已确认可用")
    memory_recall_seen_items_json = fields.TextField(
        default="[]",
        description="该 context 已注入过的记忆项摘要指纹集合(JSON)",
    )

    # 自动记忆状态
    auto_memory_last_context_msg_id = fields.IntField(default=0, description="自动记忆已处理到的最新 context_message.id")
    auto_memory_pending_count = fields.IntField(default=0, description="距上次自动记忆后累计的新聊天消息数")
    auto_memory_generating = fields.BooleanField(default=False, description="自动记忆辅助 LLM 是否正在运行")

    # tool 链状态
    tool_chain_active = fields.BooleanField(default=False, description="tool 链是否正在运行")
    tool_chain_iteration = fields.IntField(default=0, description="当前 tool 链迭代次数")

    # 权限
    permission_level = fields.CharField(
        max_length=16, default="normal",
        description="权限级别: advanced | normal",
    )

    # 时间戳
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:  # type: ignore
        table = "context_window"

    def __repr__(self) -> str:
        return f"<DBContextWindow context_id={self.context_id} owner={self.owner_type} anchor={self.active_dialog_id}>"


class DBContextDialogState(Model):
    """上下文窗口下的对话同步状态

    仅保存某个 `(context_id, dialog_chat_key)` 的增量同步水位，
    不参与上下文压缩与摘要逻辑，避免把历史消息投影误当作同步游标。
    """

    id = fields.IntField(pk=True, generated=True, description="自增 ID")

    context_id = fields.CharField(
        max_length=128,
        index=True,
        description="所属上下文窗口的 context_id",
    )
    dialog_chat_key = fields.CharField(
        max_length=128,
        index=True,
        description="来源对话窗口 chat_key",
    )
    last_synced_db_id = fields.IntField(
        default=0,
        description="该对话窗口已同步到的最新 DBChatMessage.id",
    )

    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:  # type: ignore
        table = "context_dialog_state"
        unique_together = (("context_id", "dialog_chat_key"),)

    def __repr__(self) -> str:
        return (
            f"<DBContextDialogState ctx={self.context_id} dialog={self.dialog_chat_key} "
            f"last_synced_db_id={self.last_synced_db_id}>"
        )


class DBContextMessage(Model):
    """上下文窗口内的消息记录

    独立于 DBChatMessage，专门服务于上下文窗口的历史管理。
    支持 user/assistant/tool 角色以及 tool_call 关联。
    """

    id = fields.IntField(pk=True, generated=True, description="自增 ID")

    context_id = fields.CharField(
        max_length=128, index=True,
        description="所属上下文窗口的 context_id",
    )
    role = fields.CharField(
        max_length=16,
        description="消息角色: user | assistant | tool",
    )
    sender_id = fields.CharField(max_length=128, default="", description="发送者 ID")
    sender_name = fields.CharField(max_length=128, default="", description="发送者昵称")

    # 消息内容 (JSON 序列化的 List[MessagePart])
    parts_json = fields.TextField(default="[]", description="消息内容 parts 的 JSON")

    # tool 相关
    tool_call_id = fields.CharField(max_length=128, default="", null=True, description="关联的 tool_call id")
    tool_calls_json = fields.TextField(default="", null=True, description="assistant 发出的 tool_calls JSON")

    # 来源
    source_chat_key = fields.CharField(max_length=128, default="", description="来源对话窗口")
    source_message_id = fields.CharField(max_length=64, default="", description="来源消息平台 ID")

    # 消息分类
    msg_type = fields.CharField(
        max_length=32, default="human_chat",
        description="消息类型: human_chat | bot_reply | tool_call | tool_result | system_inject | memory_inject | history_only",
    )

    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    class Meta:  # type: ignore
        table = "context_message"
        ordering = ["id"]

    def __repr__(self) -> str:
        return f"<DBContextMessage id={self.id} ctx={self.context_id} role={self.role}>"
