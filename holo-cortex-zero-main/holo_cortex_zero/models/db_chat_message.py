from typing import Dict, List, cast

import json5
from tortoise import fields
from tortoise.models import Model

from holo_cortex_zero.schemas.chat_message import (
    ChatMessageSegment,
    segments_from_list,
)

class DBChatMessage(Model):
    """数据库聊天消息模型"""

    id = fields.IntField(pk=True, generated=True, description="ID")
    sender_id = fields.CharField(max_length=128, index=True, description="发送者 ID") # -1 表示 Bot 发送的消息
    sender_name = fields.CharField(max_length=128, index=True, description="发送者真实昵称")
    sender_nickname = fields.CharField(max_length=128, index=True, description="发送者显示昵称")
    is_tome = fields.IntField(description="是否与 Bot 相关")
    is_recalled = fields.BooleanField(description="是否为撤回消息")

    adapter_key = fields.CharField(max_length=64, index=True, description="适配器标识")
    message_id = fields.CharField(max_length=64, index=True, description="消息平台 ID")
    chat_key = fields.CharField(max_length=64, index=True, description="聊天频道唯一标识")
    chat_type = fields.CharField(max_length=32, index=True, description="聊天频道类型")
    platform_userid = fields.CharField(max_length=256, index=True, description="平台用户 ID")

    content_text = fields.TextField(description="消息内容文本")
    content_data = fields.TextField(description="消息内容数据 JSON")

    ext_data = fields.TextField(description="扩展数据")

    send_timestamp = fields.IntField(index=True, description="发送时间戳")
    create_time = fields.DatetimeField(auto_now_add=True, description="创建时间")
    update_time = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:  # type: ignore
        table = "chat_message"

    def parse_content_data(self) -> List[ChatMessageSegment]:
        """解析内容数据"""
        return segments_from_list(cast(List[Dict], json5.loads(self.content_data)))
