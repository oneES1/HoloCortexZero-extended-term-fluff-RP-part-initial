"""
Telegram 适配器配置
"""

from pydantic import Field

from holo_cortex_zero.adapters.interface.base import BaseAdapterConfig
from holo_cortex_zero.core.core_utils import ExtraField
from holo_cortex_zero.schemas.i18n import i18n_text


_TELEGRAM_BOT_TOKEN_HELP = """Telegram Bot Token 获取步骤：
1. 打开 Telegram，搜索并进入官方机器人 @BotFather。
2. 给 @BotFather 发送 /newbot。
3. 按提示输入机器人显示名称，例如 HCZ Bot。
4. 再输入机器人用户名，必须以 bot 结尾，例如 hcz_zero_bot。
5. 创建成功后，@BotFather 会返回一串 Token，格式通常类似 123456789:AA...。
6. 回到这里，把这串 Token 粘贴到 Bot Token。
7. 保存配置后，重启 HCZ 后端或重建当前运行态，让 Telegram 适配器重新初始化。
8. 在 Telegram 里先给新机器人发一条 /start，再发测试消息；如果拉进群，也需要先把机器人加入目标群。

注意：Token 是机器人控制密钥，不要发到群里、不要写进公开仓库。泄露后请回到 @BotFather 用 /revoke 重新生成。"""

_TELEGRAM_BOT_TOKEN_HELP_EN = """How to get a Telegram Bot Token:
1. Open Telegram, search for the official bot @BotFather and start a chat.
2. Send /newbot to @BotFather.
3. Follow the prompts to enter a display name, e.g. HCZ Bot.
4. Then enter a username that must end with bot, e.g. hcz_zero_bot.
5. After creation, @BotFather will return a token, usually looking like 123456789:AA....
6. Paste that token into the Bot Token field here.
7. Save the config, then restart the HCZ backend or recreate the runtime to reinitialize the Telegram adapter.
8. In Telegram, send /start to the new bot first, then send a test message; if adding to a group, make sure the bot is already in the target group.

Note: The token is the bot control key. Do not share it in groups or commit it to public repos. If leaked, go back to @BotFather and use /revoke to regenerate."""


class TelegramConfig(BaseAdapterConfig):
    """Telegram 适配器配置类"""

    BOT_TOKEN: str = Field(
        default="",
        title="Bot Token",
        description="Telegram Bot API Token",
        json_schema_extra=ExtraField(
            help_label="获取 Token 指南",
            i18n_help_label=i18n_text(
                zh_CN="获取 Token 指南",
                en_US="Get Token Guide",
            ),
            help_text=_TELEGRAM_BOT_TOKEN_HELP,
            is_secret=True,
            i18n_title=i18n_text(
                zh_CN="Bot Token",
                en_US="Bot Token",
            ),
            i18n_description=i18n_text(
                zh_CN="Telegram Bot API Token",
                en_US="Telegram Bot API Token",
            ),
            i18n_help_text=i18n_text(
                zh_CN=_TELEGRAM_BOT_TOKEN_HELP,
                en_US=_TELEGRAM_BOT_TOKEN_HELP_EN,
            ),
        ).model_dump(),
    )

    PROXY_URL: str = Field(
        default="",
        title="代理地址",
        description="Telegram API 访问代理，支持 http/https/socks5 协议.空白表示不使用代理",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="代理地址",
            en_US="Proxy URL",
        ),
        i18n_description=i18n_text(
            zh_CN="Telegram API 访问代理，支持 http/https/socks5 协议.空白表示不使用代理",
            en_US="Telegram API access proxy, supports http/https/socks5. Leave blank for no proxy.",
        ),
    placeholder="例: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080").model_dump(),
    )

    OWNER_TG_USER_ID: str = Field(
        default="",
        title="你的 TG ID",
        description="Telegram 平台侧高级用户数字 user_id；框架内高级 ID 由 ADVANCED_USER_ID 决定。",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="你的 TG ID",
            en_US="Your TG User ID",
        ),
        i18n_description=i18n_text(
            zh_CN="Telegram 平台侧高级用户数字 user_id；框架内高级 ID 由 ADVANCED_USER_ID 决定。",
            en_US="Telegram platform-side advanced user numeric ID; framework advanced ID is determined by ADVANCED_USER_ID.",
        ),
    ).model_dump(),
    )
    AUTO_ACCEPT_PRIVATE_CHAT: bool = Field(
        default=True,
        title="自动接入私聊",
        description=(
            "Telegram Bot 没有接受私聊邀请动作；开启表示接收私聊 update。"
            "Telegram 也没有自动加入群聊 API，bot 被拉入群后才会收到群消息。"
            "是否回复由聊天频道 is_active 和触发逻辑决定。"
        ),
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动接入私聊",
            en_US="Auto Accept Private Chat",
        ),
        i18n_description=i18n_text(
            zh_CN=(
                "Telegram Bot 没有接受私聊邀请动作；开启表示接收私聊 update。"
                "Telegram 也没有自动加入群聊 API，bot 被拉入群后才会收到群消息。"
                "是否回复由聊天频道 is_active 和触发逻辑决定。"
            ),
            en_US=(
                "Telegram Bot has no private chat accept action; enabling means receiving private chat updates. "
                "Telegram also has no auto group join API; the bot only receives group messages after being added. "
                "Whether to reply is determined by channel is_active and trigger logic."
            ),
        ),
    ).model_dump(),
    )
