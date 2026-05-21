import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from holo_cortex_zero.services.file_system.quarantine import quarantine_file_service
from holo_cortex_zero.services.file_system.service import managed_file_service
from holo_cortex_zero.tools.common_util import (
    copy_to_upload_dir,
    download_file,
    download_file_from_base64,
    download_file_from_bytes,
)


AttachmentIngestMode = Literal["legacy_upload", "managed", "quarantine", "disabled"]


class ChatType(Enum):
    PRIVATE = "private"
    GROUP = "group"
    UNKNOWN = "unknown"


class ChatMessageSegmentType(Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    REFERENCE = "reference"
    AT = "at"
    JSON_CARD = "json_card"


class ChatMessageSegment(BaseModel):
    """聊天消息段基础文本"""

    type: ChatMessageSegmentType
    text: str

    class Config:
        use_enum_values = True


class ChatMessageSegmentAt(ChatMessageSegment):
    """聊天消息段 @"""

    target_platform_userid: str
    target_nickname: str


class ChatMessageSegmentFile(ChatMessageSegment):
    """聊天消息段文件"""

    file_name: str
    local_path: Optional[str] = None
    remote_url: Optional[str] = None
    volatile_expires_at: Optional[int] = None

    @classmethod
    def get_segment_type(cls) -> ChatMessageSegmentType:
        return ChatMessageSegmentType.FILE

    @classmethod
    async def create_from_url(
        cls,
        url: str,
        from_chat_key: str,
        file_name: str = "",
        use_suffix: str = "",
        *,
        ingest_mode: AttachmentIngestMode = "legacy_upload",
    ):
        """从 URL 创建文件消息段"""
        if url.startswith("data:"):
            return await cls.create_from_base64(url, from_chat_key, file_name, use_suffix, ingest_mode=ingest_mode)

        if ingest_mode == "disabled":
            inferred_name = file_name or managed_file_service.infer_name_from_url(url)
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {inferred_name}]",
                file_name=inferred_name,
                local_path=None,
                remote_url=None,
            )

        if ingest_mode == "managed":
            local_path, _file_name = await managed_file_service.ingest_from_url(
                url,
                from_chat_key=from_chat_key,
                file_name=file_name,
                use_suffix=use_suffix,
            )
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {file_name or _file_name}]",
                file_name=file_name or _file_name,
                local_path=local_path,
                remote_url=url,
            )

        if ingest_mode == "quarantine":
            local_path, _file_name, expires_at = await quarantine_file_service.ingest_from_url(
                url,
                from_chat_key=from_chat_key,
                file_name=file_name,
                use_suffix=use_suffix,
            )
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {_file_name}]",
                file_name=_file_name,
                local_path=local_path,
                volatile_expires_at=expires_at,
            )

        local_path, _file_name = await download_file(
            url,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        return cls(
            type=cls.get_segment_type(),
            text=f"[{cls.get_segment_type().value.capitalize()}: {file_name or _file_name}]",
            file_name=file_name or _file_name,
            local_path=local_path,
            remote_url=url,
        )

    @classmethod
    async def create_form_local_path(
        cls,
        local_path: str,
        from_chat_key: str,
        file_name: str = "",
        use_suffix: str = "",
        *,
        ingest_mode: AttachmentIngestMode = "legacy_upload",
    ):
        """从本地路径创建文件消息段"""
        if ingest_mode == "disabled":
            inferred_name = file_name or managed_file_service.sanitize_file_name(local_path.split("/")[-1] or "unknown_file")
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {inferred_name}]",
                file_name=inferred_name,
                local_path=None,
            )

        if ingest_mode == "managed":
            managed_path, _file_name = managed_file_service.ingest_from_local_path(
                local_path,
                file_name=file_name,
                use_suffix=use_suffix,
            )
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {file_name or _file_name}]",
                file_name=file_name or _file_name,
                local_path=managed_path,
            )

        if ingest_mode == "quarantine":
            quarantine_path, _file_name, expires_at = quarantine_file_service.ingest_from_local_path(
                local_path,
                file_name=file_name,
                use_suffix=use_suffix,
            )
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {_file_name}]",
                file_name=_file_name,
                local_path=quarantine_path,
                volatile_expires_at=expires_at,
            )

        upload_path, _file_name = await copy_to_upload_dir(
            file_path=local_path,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        return cls(
            type=cls.get_segment_type(),
            text=f"[{cls.get_segment_type().value.capitalize()}: {file_name or _file_name}]",
            file_name=file_name or _file_name,
            local_path=upload_path,
        )

    @classmethod
    async def create_from_bytes(
        cls,
        _bytes: bytes,
        from_chat_key: str,
        file_name: str = "",
        use_suffix: str = "",
        *,
        ingest_mode: AttachmentIngestMode = "legacy_upload",
        mime_type: str = "",
    ):
        """从字节数据创建文件消息段"""
        if ingest_mode == "disabled":
            inferred_name = file_name or (f"unknown{use_suffix}" if use_suffix else "unknown_file")
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {inferred_name}]",
                file_name=inferred_name,
                local_path=None,
            )

        if ingest_mode == "managed":
            local_path, _file_name = await managed_file_service.ingest_from_bytes(
                _bytes,
                from_chat_key=from_chat_key,
                file_name=file_name,
                use_suffix=use_suffix,
            )
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {file_name or _file_name}]",
                file_name=file_name or _file_name,
                local_path=local_path,
            )

        if ingest_mode == "quarantine":
            local_path, _file_name, expires_at = await quarantine_file_service.ingest_from_bytes(
                _bytes,
                from_chat_key=from_chat_key,
                file_name=file_name,
                use_suffix=use_suffix,
            )
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {_file_name}]",
                file_name=_file_name,
                local_path=local_path,
                volatile_expires_at=expires_at,
            )

        local_path, _file_name = await download_file_from_bytes(
            bytes_data=_bytes,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        return cls(
            type=cls.get_segment_type(),
            text=f"[{cls.get_segment_type().value.capitalize()}: {file_name or _file_name}]",
            file_name=file_name or _file_name,
            local_path=local_path,
        )

    @classmethod
    async def create_from_base64(
        cls,
        base64_str: str,
        from_chat_key: str,
        file_name: str = "",
        use_suffix: str = "",
        *,
        ingest_mode: AttachmentIngestMode = "legacy_upload",
    ):
        """从 Base64 数据创建文件消息段"""
        if ingest_mode == "disabled":
            inferred_name = file_name or (f"unknown{use_suffix}" if use_suffix else "unknown_file")
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {inferred_name}]",
                file_name=inferred_name,
                local_path=None,
            )

        if ingest_mode == "managed":
            local_path, _file_name = await managed_file_service.ingest_from_base64(
                base64_str,
                from_chat_key=from_chat_key,
                file_name=file_name,
                use_suffix=use_suffix,
            )
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {file_name or _file_name}]",
                file_name=file_name or _file_name,
                local_path=local_path,
            )

        if ingest_mode == "quarantine":
            local_path, _file_name, expires_at = await quarantine_file_service.ingest_from_base64(
                base64_str,
                from_chat_key=from_chat_key,
                file_name=file_name,
                use_suffix=use_suffix,
            )
            return cls(
                type=cls.get_segment_type(),
                text=f"[{cls.get_segment_type().value.capitalize()}: {_file_name}]",
                file_name=_file_name,
                local_path=local_path,
                volatile_expires_at=expires_at,
            )

        local_path, _file_name = await download_file_from_base64(
            base64_str=base64_str,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        return cls(
            type=cls.get_segment_type(),
            text=f"[{cls.get_segment_type().value.capitalize()}: {file_name or _file_name}]",
            file_name=file_name or _file_name,
            local_path=local_path,
        )


class ChatMessageSegmentImage(ChatMessageSegmentFile):
    """聊天消息段图片"""

    @classmethod
    def get_segment_type(cls) -> ChatMessageSegmentType:
        return ChatMessageSegmentType.IMAGE


class ChatMessageSegmentReference(ChatMessageSegment):
    """聊天消息段引用。"""

    ref_msg_id: str = ""
    ref_chat_key: str = ""
    ref_sender_id: str = ""
    ref_sender_name: str = ""
    ref_send_timestamp: int = 0
    ref_text: str = ""
    ref_segments: List[Dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def get_segment_type(cls) -> ChatMessageSegmentType:
        return ChatMessageSegmentType.REFERENCE

    def parse_ref_segments(self) -> List["ChatMessageSegment"]:
        return segments_from_list(self.ref_segments)


class ChatMessageSegmentJsonCard(ChatMessageSegment):
    """聊天消息段 JSON卡片"""

    json_data: Dict[str, Any]
    card_title: Optional[str] = None
    card_desc: Optional[str] = None
    card_icon: Optional[str] = None
    card_preview: Optional[str] = None
    card_url: Optional[str] = None
    share_from_nick: Optional[str] = None

    @classmethod
    def get_segment_type(cls) -> ChatMessageSegmentType:
        return ChatMessageSegmentType.JSON_CARD


def format_reference_timestamp(send_timestamp: int) -> str:
    if int(send_timestamp or 0) <= 0:
        return "时间未知"
    return datetime.fromtimestamp(int(send_timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def summarize_reference_segments(segments: List["ChatMessageSegment"], *, max_len: int = 120) -> str:
    text_chunks: List[str] = []
    has_image = False
    has_file = False

    for seg in segments:
        if isinstance(seg, ChatMessageSegmentReference):
            continue
        if isinstance(seg, ChatMessageSegmentImage):
            has_image = True
            continue
        if isinstance(seg, ChatMessageSegmentFile):
            has_file = True
            continue
        text = str(getattr(seg, "text", "") or "").strip()
        if text:
            text_chunks.append(text)

    combined = " ".join(chunk for chunk in text_chunks if chunk).strip()
    if combined:
        if len(combined) > max_len:
            return combined[: max(1, max_len - 1)].rstrip() + "…"
        return combined
    if has_image:
        return "[引用图片]"
    if has_file:
        return "[引用文件]"
    return "[引用消息正文未取回]"


def build_reference_segment(
    *,
    ref_msg_id: str,
    ref_chat_key: str,
    ref_sender_id: str,
    ref_sender_name: str,
    ref_send_timestamp: int,
    ref_segments: List["ChatMessageSegment"],
    max_text_len: int = 120,
    ref_text: str = "",
) -> ChatMessageSegmentReference:
    normalized_segments = [seg.model_dump() for seg in ref_segments]
    normalized_text = str(ref_text or "").strip() or summarize_reference_segments(ref_segments, max_len=max_text_len)
    return ChatMessageSegmentReference(
        type=ChatMessageSegmentType.REFERENCE,
        text=normalized_text,
        ref_msg_id=str(ref_msg_id or ""),
        ref_chat_key=str(ref_chat_key or ""),
        ref_sender_id=str(ref_sender_id or ""),
        ref_sender_name=str(ref_sender_name or ""),
        ref_send_timestamp=int(ref_send_timestamp or 0),
        ref_text=normalized_text,
        ref_segments=normalized_segments,
    )


def extract_primary_reference_segment(segments: List["ChatMessageSegment"]) -> Optional[ChatMessageSegmentReference]:
    for seg in segments:
        if isinstance(seg, ChatMessageSegmentReference):
            return seg
    return None


def segment_from_dict(data: Dict) -> ChatMessageSegment:
    """根据字典数据创建聊天消息段"""
    segment_type = ChatMessageSegmentType(data["type"])
    if segment_type == ChatMessageSegmentType.TEXT:
        return ChatMessageSegment.model_validate(data)
    if segment_type == ChatMessageSegmentType.IMAGE:
        return ChatMessageSegmentImage.model_validate(data)
    if segment_type == ChatMessageSegmentType.FILE:
        return ChatMessageSegmentFile.model_validate(data)
    if segment_type == ChatMessageSegmentType.REFERENCE:
        return ChatMessageSegmentReference.model_validate(data)
    if segment_type == ChatMessageSegmentType.AT:
        return ChatMessageSegmentAt.model_validate(data)
    if segment_type == ChatMessageSegmentType.JSON_CARD:
        return ChatMessageSegmentJsonCard.model_validate(data)
    raise ValueError(f"Unsupported segment type: {segment_type}")


def segments_from_list(data: List[Dict]) -> List[ChatMessageSegment]:
    """根据列表数据创建聊天消息段列表"""
    return [segment_from_dict(item) for item in data]


class ChatMessage(BaseModel):
    """聊天消息"""

    message_id: str
    sender_id: str
    sender_name: str
    sender_nickname: str
    adapter_key: str
    platform_userid: Optional[str]
    is_tome: Optional[int] = 0
    is_recalled: Optional[bool] = False

    chat_key: str
    chat_type: ChatType
    content_text: str
    content_data: List[ChatMessageSegment]

    ext_data: Dict[str, Any]

    send_timestamp: int

    class Config:
        use_enum_values = True

    @classmethod
    def create_empty(cls, chat_key: str) -> "ChatMessage":
        return cls(
            message_id="",
            sender_id="",
            sender_name="",
            sender_nickname="",
            adapter_key="",
            platform_userid="",
            is_tome=0,
            is_recalled=False,
            chat_key=chat_key,
            chat_type=ChatType.UNKNOWN,
            content_text="",
            content_data=[],
            ext_data={},
            send_timestamp=int(time.time()),
        )

    def is_empty(self) -> bool:
        return (
            not self.message_id
            and not self.sender_id
            and not self.sender_name
            and not self.sender_nickname
            and not self.adapter_key
            and not self.platform_userid
            and not self.content_text
            and not self.content_data
        )
