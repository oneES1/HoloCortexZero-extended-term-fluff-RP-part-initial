"""Shared adapter identity canonicalization.

Mainline: adapters receive and send platform protocol details. This module is
the only ingress layer that maps platform-side owner ids to the HCZ canonical
advanced identity. Commands, context routing and file policy remain framework
business logic after this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from holo_cortex_zero.adapters.interface.schemas.extra import PlatformMessageExt
from holo_cortex_zero.adapters.interface.schemas.platform import PlatformChannel, PlatformMessage, PlatformUser
from holo_cortex_zero.core import config
from holo_cortex_zero.core.runtime_identity import (
    get_primary_advanced_user_display_name,
    get_primary_advanced_user_id,
)
from holo_cortex_zero.schemas.chat_message import ChatType

if TYPE_CHECKING:
    from holo_cortex_zero.adapters.interface.base import BaseAdapter


@dataclass(frozen=True)
class CanonicalInboundIdentity:
    platform_user: PlatformUser
    platform_channel: PlatformChannel
    platform_message: PlatformMessage
    raw_platform_userid: str
    raw_channel_id: str
    canonical_userid: str
    canonical_channel_id: str
    is_primary_advanced_user: bool
    identity_mapped: bool


@dataclass(frozen=True)
class CanonicalIdentityPreview:
    raw_platform_userid: str
    raw_channel_id: str
    canonical_userid: str
    canonical_channel_id: str
    canonical_chat_key: str
    is_primary_advanced_user: bool
    identity_mapped: bool


def _is_private_channel(channel: PlatformChannel) -> bool:
    raw_type = getattr(channel, "channel_type", "")
    if raw_type == ChatType.PRIVATE:
        return True
    return str(getattr(raw_type, "value", raw_type or "")).strip().lower() == ChatType.PRIVATE.value


def merge_identity_ext(
    ext_data: PlatformMessageExt | None,
    *,
    raw_platform_userid: str,
    raw_channel_id: str,
    identity_mapped: bool,
) -> PlatformMessageExt:
    merged = ext_data.model_copy(deep=True) if ext_data else PlatformMessageExt()
    merged.raw_platform_userid = raw_platform_userid
    merged.raw_channel_id = raw_channel_id
    merged.identity_mapped = identity_mapped
    return merged


def preview_canonical_inbound_identity(
    *,
    adapter: "BaseAdapter",
    raw_platform_userid: str,
    raw_channel_id: str,
    channel_type: ChatType,
) -> CanonicalIdentityPreview:
    raw_userid = str(raw_platform_userid or "").strip()
    raw_channel = str(raw_channel_id or "").strip()
    is_primary_advanced_user = adapter.is_primary_advanced_platform_user(raw_userid)

    canonical_userid = raw_userid
    canonical_channel_id = raw_channel
    identity_mapped = False

    if is_primary_advanced_user:
        canonical_userid = get_primary_advanced_user_id(config)
        identity_mapped = canonical_userid != raw_userid
        if channel_type == ChatType.PRIVATE:
            canonical_channel_id = adapter.canonical_private_channel_id()
            identity_mapped = identity_mapped or canonical_channel_id != raw_channel

    return CanonicalIdentityPreview(
        raw_platform_userid=raw_userid,
        raw_channel_id=raw_channel,
        canonical_userid=canonical_userid,
        canonical_channel_id=canonical_channel_id,
        canonical_chat_key=f"{adapter.key}-{canonical_channel_id}",
        is_primary_advanced_user=is_primary_advanced_user,
        identity_mapped=identity_mapped,
    )


def canonicalize_inbound_identity(
    *,
    adapter: "BaseAdapter",
    platform_user: PlatformUser,
    platform_channel: PlatformChannel,
    platform_message: PlatformMessage,
) -> CanonicalInboundIdentity:
    raw_platform_userid = str(platform_user.user_id or platform_message.sender_id or "").strip()
    raw_channel_id = str(platform_channel.channel_id or "").strip()
    channel_type = platform_channel.channel_type
    preview = preview_canonical_inbound_identity(
        adapter=adapter,
        raw_platform_userid=raw_platform_userid,
        raw_channel_id=raw_channel_id,
        channel_type=channel_type,
    )
    is_primary_advanced_user = preview.is_primary_advanced_user

    canonical_user = platform_user.model_copy(deep=True)
    canonical_channel = platform_channel.model_copy(deep=True)
    canonical_message = platform_message.model_copy(deep=True)

    canonical_userid = preview.canonical_userid
    canonical_channel_id = preview.canonical_channel_id
    identity_mapped = preview.identity_mapped

    if is_primary_advanced_user:
        display_name = get_primary_advanced_user_display_name(config)
        canonical_user.user_id = canonical_userid
        canonical_user.user_name = display_name
        canonical_message.sender_id = canonical_userid
        canonical_message.sender_name = display_name
        canonical_message.sender_nickname = display_name
        if _is_private_channel(platform_channel):
            canonical_channel.channel_id = canonical_channel_id

    canonical_message.ext_data = merge_identity_ext(
        canonical_message.ext_data,
        raw_platform_userid=raw_platform_userid,
        raw_channel_id=raw_channel_id,
        identity_mapped=identity_mapped,
    )

    return CanonicalInboundIdentity(
        platform_user=canonical_user,
        platform_channel=canonical_channel,
        platform_message=canonical_message,
        raw_platform_userid=raw_platform_userid,
        raw_channel_id=raw_channel_id,
        canonical_userid=canonical_userid,
        canonical_channel_id=canonical_channel_id,
        is_primary_advanced_user=is_primary_advanced_user,
        identity_mapped=identity_mapped,
    )
