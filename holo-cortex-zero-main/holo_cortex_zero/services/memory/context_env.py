from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from holo_cortex_zero.api.schemas import AgentCtx
from holo_cortex_zero.core import config
from holo_cortex_zero.core.runtime_identity import get_primary_advanced_user_id, is_advanced_user_id


@dataclass(frozen=True)
class MemoryDialogEnv:
    source_chat_key: str
    channel_type: str
    channel_id: str
    peer_id: str
    hp_private_flag: str
    chat_env_system: str
    chat_env_note: str


def build_memory_dialog_env_from_chat_key(chat_key: str) -> MemoryDialogEnv:
    normalized_chat_key = str(chat_key or "").strip()
    channel_type = ""
    channel_id = ""
    chat_key_lower = normalized_chat_key.lower()

    if chat_key_lower.startswith("private_"):
        channel_type = "private"
        channel_id = normalized_chat_key.split("_", 1)[1]
    elif chat_key_lower.startswith("group_"):
        channel_type = "group"
        channel_id = normalized_chat_key.split("_", 1)[1]
    elif "-private_" in chat_key_lower:
        channel_type = "private"
        channel_id = normalized_chat_key.rsplit("-private_", 1)[1]
    elif "-group_" in chat_key_lower:
        channel_type = "group"
        channel_id = normalized_chat_key.rsplit("-group_", 1)[1]

    peer_digits = "".join([ch for ch in channel_id if ch.isdigit()])
    peer_id = peer_digits if peer_digits else channel_id
    hp_private_flag = "未知"

    if channel_type == "private":
        if peer_id and peer_id.isdigit():
            hp_private_flag = "是" if is_advanced_user_id(peer_id, config) else "否"
        if hp_private_flag == "是":
            chat_env_system = "**内部System标注：高级用户私聊**"
            chat_env_note = f"高级用户私聊({get_primary_advanced_user_id(config)})"
        elif hp_private_flag == "否":
            chat_env_system = "**内部System标注：陌生人私聊**"
            chat_env_note = "陌生人私聊"
        else:
            chat_env_system = "**内部System标注：私聊**"
            chat_env_note = "私聊"
    elif channel_type == "group":
        chat_env_system = "**内部System标注**"
        chat_env_note = "群聊"
    else:
        chat_env_system = "**内部System标注：未知环境**"
        chat_env_note = "未知环境"

    return MemoryDialogEnv(
        source_chat_key=normalized_chat_key,
        channel_type=channel_type,
        channel_id=channel_id,
        peer_id=peer_id,
        hp_private_flag=hp_private_flag,
        chat_env_system=chat_env_system,
        chat_env_note=chat_env_note,
    )


def build_memory_dialog_env_from_ctx(_ctx: AgentCtx, *, context_chat_key: str = "") -> MemoryDialogEnv:
    raw_channel_type = getattr(_ctx, "channel_type", None)
    if isinstance(raw_channel_type, str):
        channel_type = raw_channel_type.strip().lower()
    else:
        try:
            enum_val = getattr(raw_channel_type, "value", None)
        except Exception:
            enum_val = None
        channel_type = str(enum_val if enum_val is not None else (raw_channel_type or "")).strip().lower()

    if channel_type not in {"private", "group"}:
        channel_type = ""

    channel_id = str(getattr(_ctx, "channel_id", "") or "").strip()
    chat_key = str(context_chat_key or getattr(_ctx, "from_chat_key", "") or getattr(_ctx, "chat_key", "") or "").strip()

    env = build_memory_dialog_env_from_chat_key(chat_key)
    if channel_type and channel_type != env.channel_type:
        env = MemoryDialogEnv(
            source_chat_key=chat_key,
            channel_type=channel_type,
            channel_id=channel_id or env.channel_id,
            peer_id=env.peer_id,
            hp_private_flag=env.hp_private_flag,
            chat_env_system=env.chat_env_system,
            chat_env_note=env.chat_env_note,
        )
        # recompute using explicit ctx values for stronger correctness
        env = build_memory_dialog_env_from_chat_key(
            f"{getattr(_ctx, 'adapter_key', '')}-{channel_type}_{channel_id}" if channel_id else chat_key
        )
    elif channel_id and channel_id != env.channel_id:
        env = build_memory_dialog_env_from_chat_key(
            f"{getattr(_ctx, 'adapter_key', '')}-{channel_type}_{channel_id}" if channel_type else chat_key
        )
    return env
