"""Matrix adapter config."""

from pydantic import Field

from holo_cortex_zero.adapters.interface.base import BaseAdapterConfig
from holo_cortex_zero.core.core_utils import ExtraField
from holo_cortex_zero.schemas.i18n import i18n_text


class MatrixConfig(BaseAdapterConfig):
    """Matrix adapter configuration.

    Mainline rule:
    - Matrix protocol ids stay inside the adapter.
    - HCZ advanced identity is mapped by the shared adapter interface from
      ADVANCED_USER_ID / ADVANCED_USER_DISPLAY_NAME.
    """

    HOMESERVER_URL: str = Field(
        default="",
        title="Matrix Homeserver URL",
        description="Matrix homeserver client API base URL.",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="Matrix Homeserver URL",
            en_US="Matrix Homeserver URL",
        ),
        i18n_description=i18n_text(
            zh_CN="Matrix homeserver client API base URL.",
            en_US="Matrix homeserver client API base URL.",
        ),
    ).model_dump(),
    )
    PROXY_URL: str = Field(
        default="",
        title="Matrix Proxy URL",
        description="Matrix adapter proxy URL. Empty means direct connection.",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="Matrix Proxy URL",
            en_US="Matrix Proxy URL",
        ),
        i18n_description=i18n_text(
            zh_CN="Matrix adapter proxy URL. Empty means direct connection.",
            en_US="Matrix adapter proxy URL. Empty means direct connection.",
        ),
    placeholder="例: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080").model_dump(),
    )
    BOT_USER_ID: str = Field(
        default="",
        title="Bot Matrix User ID",
        description="Matrix bot account, e.g. @hcz:holocortexzero.com.",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="Bot Matrix User ID",
            en_US="Bot Matrix User ID",
        ),
        i18n_description=i18n_text(
            zh_CN="Matrix bot account, e.g. @hcz:holocortexzero.com.",
            en_US="Matrix bot account, e.g. @hcz:holocortexzero.com.",
        ),
    ).model_dump(),
    )
    BOT_PASSWORD: str = Field(
        default="",
        title="Bot Password",
        description="Bot password used when BOT_ACCESS_TOKEN is empty.",
        json_schema_extra=ExtraField(
            is_secret=True,
            i18n_title=i18n_text(
                zh_CN="Bot Password",
                en_US="Bot Password",
            ),
            i18n_description=i18n_text(
                zh_CN="Bot password used when BOT_ACCESS_TOKEN is empty.",
                en_US="Bot password used when BOT_ACCESS_TOKEN is empty.",
            ),
        ).model_dump(),
    )
    BOT_ACCESS_TOKEN: str = Field(
        default="",
        title="Bot Access Token",
        description="Matrix access token. Preferred for long-running production; SDK restore_login will use DEVICE_ID with this token.",
        json_schema_extra=ExtraField(
            is_secret=True,
            i18n_title=i18n_text(
                zh_CN="Bot Access Token",
                en_US="Bot Access Token",
            ),
            i18n_description=i18n_text(
                zh_CN="Matrix access token. Preferred for long-running production; SDK restore_login will use DEVICE_ID with this token.",
                en_US="Matrix access token. Preferred for long-running production; SDK restore_login will use DEVICE_ID with this token.",
            ),
        ).model_dump(),
    )
    DEVICE_ID: str = Field(
        default="HCZ_MATRIX_ADAPTER",
        title="Device ID",
        description="Stable Matrix device id for SDK login and E2EE crypto store.",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="Device ID",
            en_US="Device ID",
        ),
        i18n_description=i18n_text(
            zh_CN="Stable Matrix device id for SDK login and E2EE crypto store.",
            en_US="Stable Matrix device ID for SDK login and E2EE crypto store.",
        ),
    ).model_dump(),
    )
    CRYPTO_STORE_PATH: str = Field(
        default="crypto_store",
        title="Crypto Store Path",
        description="matrix-nio E2EE crypto store path. Relative paths are stored under the Matrix adapter config directory.",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="Crypto Store Path",
            en_US="Crypto Store Path",
        ),
        i18n_description=i18n_text(
            zh_CN="matrix-nio E2EE crypto store path. Relative paths are stored under the Matrix adapter config directory.",
            en_US="matrix-nio E2EE crypto store path. Relative paths are stored under the Matrix adapter config directory.",
        ),
    ).model_dump(),
    )
    IGNORE_UNVERIFIED_DEVICES: bool = Field(
        default=True,
        title="Ignore Unverified Devices",
        description="When sending to encrypted rooms, allow matrix-nio to send to unverified devices. Recommended true for open deployments without manual device verification.",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="Ignore Unverified Devices",
            en_US="Ignore Unverified Devices",
        ),
        i18n_description=i18n_text(
            zh_CN="When sending to encrypted rooms, allow matrix-nio to send to unverified devices. Recommended true for open deployments without manual device verification.",
            en_US="When sending to encrypted rooms, allow matrix-nio to send to unverified devices. Recommended true for open deployments without manual device verification.",
        ),
    ).model_dump(),
    )

    OWNER_MATRIX_USER_ID: str = Field(
        default="",
        title="你的 Element(Matrix客户端) ID",
        description="Matrix 平台侧高级用户 ID；框架内高级 ID 由 ADVANCED_USER_ID 决定。",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="你的 Element(Matrix客户端) ID",
            en_US="Your Element (Matrix) ID",
        ),
        i18n_description=i18n_text(
            zh_CN="Matrix 平台侧高级用户 ID；框架内高级 ID 由 ADVANCED_USER_ID 决定。",
            en_US="Matrix platform-side advanced user ID; framework advanced ID is determined by ADVANCED_USER_ID.",
        ),
    ).model_dump(),
    )
    AUTO_JOIN_PRIVATE_INVITE: bool = Field(
        default=True,
        title="自动加入私聊邀请",
        description="自动加入私聊邀请。是否回复由聊天频道 is_active 和触发逻辑决定。",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动加入私聊邀请",
            en_US="Auto Join Private Invite",
        ),
        i18n_description=i18n_text(
            zh_CN="自动加入私聊邀请。是否回复由聊天频道 is_active 和触发逻辑决定。",
            en_US="Auto join private chat invites. Whether to reply is determined by channel is_active and trigger logic.",
        ),
    ).model_dump(),
    )
    AUTO_JOIN_GROUP_INVITE: bool = Field(
        default=False,
        title="自动加入群聊邀请",
        description="默认关闭；开启后自动加入群聊邀请。是否回复由聊天频道 is_active 和触发逻辑决定。",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动加入群聊邀请",
            en_US="Auto Join Group Invite",
        ),
        i18n_description=i18n_text(
            zh_CN="默认关闭；开启后自动加入群聊邀请。是否回复由聊天频道 is_active 和触发逻辑决定。",
            en_US="Default off; enable to auto join group chat invites. Whether to reply is determined by channel is_active and trigger logic.",
        ),
    ).model_dump(),
    )
    SYNC_TIMEOUT_MS: int = Field(
        default=30000,
        title="Sync 超时毫秒",
        description="Matrix /sync 长轮询超时时间。",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="Sync 超时毫秒",
                en_US="Sync Timeout (ms)",
            ),
            i18n_description=i18n_text(
                zh_CN="Matrix /sync 长轮询超时时间。",
                en_US="Matrix /sync long-polling timeout.",
            ),
        ).model_dump(),
    )
    REQUEST_TIMEOUT_SECONDS: float = Field(
        default=40.0,
        title="请求超时秒",
        description="Matrix HTTP 请求超时。",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="请求超时秒",
                en_US="Request Timeout (seconds)",
            ),
            i18n_description=i18n_text(
                zh_CN="Matrix HTTP 请求超时。",
                en_US="Matrix HTTP request timeout.",
            ),
        ).model_dump(),
    )
    STATE_FILE: str = Field(
        default="room_map.json",
        title="房间映射状态文件",
        description="保存 HCZ channel_id 到 Matrix room_id 的映射；位于 adapter config 目录。",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="房间映射状态文件",
            en_US="Room Mapping State File",
        ),
        i18n_description=i18n_text(
            zh_CN="保存 HCZ channel_id 到 Matrix room_id 的映射；位于 adapter config 目录。",
            en_US="Stores HCZ channel_id to Matrix room_id mapping; located in adapter config directory.",
        ),
    ).model_dump(),
    )
    LOG_RAW_EVENT_SUMMARY: bool = Field(
        default=False,
        title="记录原始事件摘要",
        description="调试用，仅记录事件摘要，不记录完整消息体。",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )
