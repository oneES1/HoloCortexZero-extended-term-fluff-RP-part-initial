from pydantic import BaseModel


class PlatformMessageExt(BaseModel):
    """平台消息扩展数据"""

    ref_chat_key: str = ""  # 引用聊天频道唯一标识
    ref_msg_id: str = ""  # 引用消息的平台消息 ID
    ref_sender_id: str = ""  # 引用消息的发送者平台 ID
    raw_platform_userid: str = ""  # 适配器收到的平台真实用户 ID
    raw_channel_id: str = ""  # 适配器收到的平台真实频道 ID
    identity_mapped: bool = False  # 是否在主干身份层映射到 HCZ 高级用户
    native_voice: bool = False  # 是否为平台原生语音消息，不等同普通音频文件
