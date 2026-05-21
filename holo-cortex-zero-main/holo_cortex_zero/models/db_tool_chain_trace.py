from enum import IntEnum

from tortoise import fields
from tortoise.models import Model


class ToolChainTraceStopType(IntEnum):
    """Tool 链运行停止类型"""

    NORMAL = 0
    ERROR = 1
    TIMEOUT = 2
    AGENT = 8
    MANUAL = 9
    SECURITY = 10
    MULTIMODAL_AGENT = 11


class DBToolChainTrace(Model):
    """新架构 Tool 链运行轨迹

    独立于历史 `exec_code` 记录，仅服务于新架构：
    - 一次用户触发对应一条运行记录
    - 详细事件序列写入 `trace_json`
    - 列表检索所需摘要字段做显式列存储
    """

    id = fields.IntField(pk=True, generated=True, description="ID")
    context_id = fields.CharField(max_length=128, index=True, description="上下文窗口 ID")
    trigger_chat_key = fields.CharField(max_length=128, index=True, description="触发对话窗口")
    active_dialog_id = fields.CharField(max_length=128, default="", description="实际回复对话窗口")
    permission_level = fields.CharField(max_length=16, default="normal", description="权限级别")

    trigger_user_id = fields.CharField(max_length=256, default="0", index=True, description="触发用户 ID")
    trigger_user_name = fields.CharField(max_length=128, default="System", description="触发用户名")
    trigger_message_text = fields.TextField(default="", description="触发消息文本")
    summary_text = fields.TextField(default="", description="本次运行摘要")

    success = fields.BooleanField(default=False, description="是否成功")
    stop_type = fields.IntEnumField(
        ToolChainTraceStopType,
        default=ToolChainTraceStopType.NORMAL,
        description="停止类型",
    )

    llm_duration_ms = fields.IntField(default=0, description="LLM 总耗时(毫秒)")
    tool_duration_ms = fields.IntField(default=0, description="Tool 总耗时(毫秒)")
    total_duration_ms = fields.IntField(default=0, description="总耗时(毫秒)")
    total_iterations = fields.IntField(default=0, description="总轮次")

    use_model = fields.CharField(max_length=256, default="", description="本次使用模型摘要")
    token_input = fields.IntField(default=0, description="输入 token")
    token_output = fields.IntField(default=0, description="输出 token")
    token_total = fields.IntField(default=0, description="总 token")

    trace_json = fields.TextField(default="{}", description="完整运行轨迹 JSON")

    create_time = fields.DatetimeField(auto_now_add=True, description="创建时间")
    update_time = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:  # type: ignore
        table = "tool_chain_trace"
