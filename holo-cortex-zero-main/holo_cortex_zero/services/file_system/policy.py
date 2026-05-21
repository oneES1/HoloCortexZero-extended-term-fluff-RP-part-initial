from __future__ import annotations

from typing import Any, Literal

from holo_cortex_zero.core import config
from holo_cortex_zero.core.runtime_identity import is_advanced_user_id


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


AttachmentIngestMode = Literal["legacy_upload", "managed", "quarantine", "disabled"]


def resolve_incoming_attachment_mode(
    *,
    adapter_key: str,
    chat_key: str,
    chat_type: str,
    sender_id: Any,
    platform_userid: Any,
    attachment_kind: str,
    channel_type: Any = None,
) -> tuple[AttachmentIngestMode, str]:
    """解析附件进入框架的接收模式。

    主干规则：
    - 高级用户 → managed（进入高级文件系统）
    - 普通用户 image → quarantine（隔离落盘 48 小时，不暴露高级文件路径）
    - 普通用户 file/audio/video → disabled
    """

    normalized_sender = _normalize_text(sender_id)
    normalized_platform_userid = _normalize_text(platform_userid)
    normalized_chat_type = (_normalize_text(channel_type) or _normalize_text(chat_type)).lower()
    normalized_kind = _normalize_text(attachment_kind).lower() or "file"

    is_owner = is_advanced_user_id(normalized_sender, config) or is_advanced_user_id(normalized_platform_userid, config)
    if is_owner:
        if normalized_chat_type == "private":
            return "managed", "owner_private"
        if normalized_chat_type == "group":
            return "managed", "owner_group"
        return "disabled", f"rejected:unsupported_chat_type:{normalized_chat_type or 'unknown'}"

    if normalized_kind == "image" and bool(getattr(config, "NORMAL_USER_IMAGE_QUARANTINE_ENABLE", True)):
        return "quarantine", "normal_user_image_quarantine"

    if normalized_kind == "image":
        return "disabled", "normal_user_image_disabled"

    return "disabled", f"normal_user_{normalized_kind or 'file'}_disabled"
