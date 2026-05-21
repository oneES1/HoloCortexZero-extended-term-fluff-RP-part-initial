import base64
import hashlib
import re
import shutil
from pathlib import Path
from typing import List, Optional, Type

from fastapi import APIRouter
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from pydantic import Field

from holo_cortex_zero.adapters.interface.schemas.platform import (
    PlatformChannel,
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformSendSegmentType,
    PlatformUser,
)
from holo_cortex_zero.adapters.onebot_v11.matchers.message import register_matcher
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.core_utils import ExtraField
from holo_cortex_zero.core.os_env import NAPCAT_TEMPFILE_DIR, OsEnv
from holo_cortex_zero.core.runtime_identity import get_primary_advanced_user_id
from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.schemas.chat_message import ChatType
from holo_cortex_zero.schemas.i18n import i18n_text

from ..interface.base import AdapterMetadata, BaseAdapter, BaseAdapterConfig
from .core.bot import get_bot
from .tools.at_parser import SegAt, parse_at_from_text
from .tools.convertor import get_channel_type


class OnebotV11Config(BaseAdapterConfig):
    """Onebot V11 适配器配置"""

    SESSION_ENABLE_AT: bool = Field(
        default=True,
        title="启用 @用户 功能",
        description="关闭后 AI 发送的 @用户 消息将被解析为纯文本用户名，避免反复打扰用户",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="启用 @用户 功能",
            en_US="Enable @User Feature",
        ),
        i18n_description=i18n_text(
            zh_CN="关闭后 AI 发送的 @用户 消息将被解析为纯文本用户名，避免反复打扰用户",
            en_US="When disabled, AI @user messages will be parsed as plain text usernames to avoid repeatedly disturbing users.",
        ),
    ).model_dump(),
    )
    SESSION_PROCESSING_WITH_EMOJI: bool = Field(
        default=True,
        title="显示处理中表情反馈",
        description="当 AI 开始处理消息时，对应消息会显示处理中表情反馈",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="显示处理中表情反馈",
            en_US="Show Processing Emoji Feedback",
        ),
        i18n_description=i18n_text(
            zh_CN="当 AI 开始处理消息时，对应消息会显示处理中表情反馈",
            en_US="When AI starts processing a message, the corresponding message will show a processing emoji feedback.",
        ),
    ).model_dump(),
    )
    BOT_QQ: str = Field(
        default="",
        title="机器人 QQ 号",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="机器人 QQ 号",
            en_US="Bot QQ Number",
        ),
    ).model_dump(),
    )
    OWNER_QQ_USER_ID: str = Field(
        default="",
        title="你的QQ ID",
        description="QQ/OneBot 平台侧高级用户 QQ 号；框架内高级 ID 由 ADVANCED_USER_ID 决定。",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="你的QQ ID",
            en_US="Your QQ ID",
        ),
        i18n_description=i18n_text(
            zh_CN="QQ/OneBot 平台侧高级用户 QQ 号；框架内高级 ID 由 ADVANCED_USER_ID 决定。",
            en_US="QQ/OneBot platform-side advanced user QQ number; framework advanced ID is determined by ADVANCED_USER_ID.",
        ),
    ).model_dump(),
    )
    AUTO_ACCEPT_PRIVATE_REQUEST: bool = Field(
        default=True,
        title="自动接受私聊好友请求",
        description="自动接受真实高级用户和普通用户的好友请求。是否回复由聊天频道 is_active 和触发逻辑决定。",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动接受私聊好友请求",
            en_US="Auto Accept Private Friend Request",
        ),
        i18n_description=i18n_text(
            zh_CN="自动接受真实高级用户和普通用户的好友请求。是否回复由聊天频道 is_active 和触发逻辑决定。",
            en_US="Auto accept friend requests from real advanced users and normal users. Whether to reply is determined by channel is_active and trigger logic.",
        ),
    ).model_dump(),
    )
    AUTO_ACCEPT_GROUP_REQUEST: bool = Field(
        default=False,
        title="自动接受群聊邀请",
        description="默认不自动接受群聊邀请或加群请求。",
    json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动接受群聊邀请",
            en_US="Auto Accept Group Invite",
        ),
        i18n_description=i18n_text(
            zh_CN="默认不自动接受群聊邀请或加群请求。",
            en_US="By default, do not auto accept group chat invites or join requests.",
        ),
    ).model_dump(),
    )
    """NAPCAT 配置"""
    NAPCAT_ACCESS_URL: str = Field(
        default="/napcat/webui/web_login",
        title="NapCat WebUI 访问地址",
        description="NapCat 的 WebUI 外部访问路径。默认走 HCZ 内置 /napcat 反代，不需要暴露 NapCat 端口。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="NapCat WebUI 访问地址",
            en_US="NapCat WebUI Access URL",
        ),
        i18n_description=i18n_text(
            zh_CN="NapCat 的 WebUI 外部访问路径。默认走 HCZ 内置 /napcat 反代，不需要暴露 NapCat 端口。",
            en_US="NapCat WebUI external access path. Defaults to HCZ built-in /napcat reverse proxy; no need to expose NapCat port.",
        ),
    placeholder="例: /napcat/webui/web_login").model_dump(),
    )
    NAPCAT_PROXY_BASE_URL: str = Field(
        default="http://hcz_napcat:65535",
        title="NapCat 内部代理地址",
        description="HCZ 后端访问 NapCat WebUI 的内部地址；Docker 部署默认走同一 compose 网络。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="NapCat 内部代理地址",
            en_US="NapCat Internal Proxy URL",
        ),
        i18n_description=i18n_text(
            zh_CN="HCZ 后端访问 NapCat WebUI 的内部地址；Docker 部署默认走同一 compose 网络。",
            en_US="HCZ backend internal address for accessing NapCat WebUI; Docker deployments default to the same compose network.",
        ),
    placeholder="例: http://hcz_napcat:65535").model_dump(),
    )
    NAPCAT_CONTAINER_NAME: str = Field(
        default="hcz_napcat",
        title="NapCat 容器名称",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="NapCat 容器名称",
                en_US="NapCat Container Name",
            ),
        ).model_dump(),
    )


_NAPCAT_CONTAINER_QQ_ROOT = Path("/app/.config/QQ")
_NAPCAT_CONTAINER_TEMP_ROOT = _NAPCAT_CONTAINER_QQ_ROOT / "NapCat" / "temp"
_NAPCAT_HOST_QQ_ROOT = Path(NAPCAT_TEMPFILE_DIR).parent.parent


def _relative_to_or_none(candidate: Path, root: Path) -> Optional[Path]:
    try:
        return candidate.relative_to(root)
    except Exception:
        return None


def _resolve_onebot_file_path(file_path: Path) -> Path:
    source_path = file_path.expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"OneBot 本地文件不存在或不是普通文件: {source_path}")

    workspace_relative = _relative_to_or_none(source_path, Path(OsEnv.WORKSPACE_ROOT).resolve())
    if workspace_relative is not None:
        resolved_path = Path("/workspace") / workspace_relative
        logger.info(f"OneBot 本地文件直连 workspace: raw={source_path} resolved={resolved_path}")
        return resolved_path

    napcat_relative = _relative_to_or_none(source_path, _NAPCAT_HOST_QQ_ROOT.resolve())
    if napcat_relative is not None:
        resolved_path = _NAPCAT_CONTAINER_QQ_ROOT / napcat_relative
        logger.info(f"OneBot 本地文件直连 NapCat QQ 目录: raw={source_path} resolved={resolved_path}")
        return resolved_path

    napcat_temp_root = Path(NAPCAT_TEMPFILE_DIR).resolve()
    napcat_temp_root.mkdir(parents=True, exist_ok=True)
    source_stat = source_path.stat()
    digest = hashlib.sha256(
        f"{source_path}|{source_stat.st_size}|{source_stat.st_mtime_ns}".encode("utf-8", errors="ignore")
    ).hexdigest()[:16]
    suffix = source_path.suffix
    stem = source_path.stem or "file"
    materialized_name = f"{stem}_{digest}{suffix}"
    materialized_host_path = napcat_temp_root / materialized_name

    should_copy = True
    if materialized_host_path.exists():
        existing_stat = materialized_host_path.stat()
        should_copy = (
            existing_stat.st_size != source_stat.st_size
            or existing_stat.st_mtime_ns < source_stat.st_mtime_ns
        )

    if should_copy:
        shutil.copy2(source_path, materialized_host_path)
        logger.info(
            f"OneBot 本地文件已物化到 NapCat temp: raw={source_path} materialized={materialized_host_path}"
        )
    else:
        logger.info(
            f"OneBot 复用已物化 NapCat temp 文件: raw={source_path} materialized={materialized_host_path}"
        )

    return _NAPCAT_CONTAINER_TEMP_ROOT / materialized_name


def _resolve_onebot_file_uri(file_path: Path) -> str:
    resolved_path = _resolve_onebot_file_path(file_path)
    return resolved_path.as_uri()


class OnebotV11Adapter(BaseAdapter[OnebotV11Config]):
    """OneBot V11 适配器"""

    def __init__(self, config_cls: Type[OnebotV11Config] = OnebotV11Config):
        """初始化OnebotV11适配器"""
        super().__init__(config_cls)

    @property
    def key(self) -> str:
        return "onebot_v11"

    @property
    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="OneBot V11",
            description="OneBot V11 协议适配器，支持与兼容 OneBot V11 标准的 QQ 机器人实现进行通信",
            version="1.0.0",
            author="HoloCortexZero",
            tags=["qq", "onebot", "v11", "chat", "messaging"],
        )

    @property
    def chat_key_rules(self) -> List[str]:
        return [
            "群聊: `onebot_v11-group_123456` (123456为群号)",
            "私聊: `onebot_v11-private_123456` (123456为用户QQ号)",
        ]

    def get_adapter_router(self) -> APIRouter:
        """获取适配器路由"""
        from .routers import router

        return router

    def get_primary_advanced_platform_user_ids(self) -> set[str]:
        uid = str(getattr(self.config, "OWNER_QQ_USER_ID", "") or "").strip()
        return {uid} if uid else set()

    async def init(self) -> None:
        """初始化适配器"""
        from . import matchers

        register_matcher(self)

    async def cleanup(self) -> None:
        """清理适配器"""
        return

    async def forward_message(self, request: PlatformSendRequest) -> PlatformSendResponse:
        """推送消息到 OneBot V11 协议端"""

        message_id: Optional[str] = None

        # 分离文件类型和其他类型的消息段
        file_segments = [seg for seg in request.segments if seg.type == PlatformSendSegmentType.FILE]
        other_segments = [seg for seg in request.segments if seg.type != PlatformSendSegmentType.FILE]

        # 先发送文件（如果有）
        if file_segments:
            await self._send_files(request.chat_key, file_segments)

        # 再发送其他类型消息（如果有）
        if other_segments:
            modified_request = PlatformSendRequest(
                chat_key=request.chat_key,
                segments=other_segments,
                ref_msg_id=request.ref_msg_id,
            )
            message_id = await self._send_message(modified_request)

        return PlatformSendResponse(success=True, message_id=message_id)

    async def _send_message(self, request: PlatformSendRequest) -> Optional[str]:
        """发送普通消息（文本、@、图片等）"""
        message = Message()

        if request.ref_msg_id:
            message.append(MessageSegment.reply(id_=int(request.ref_msg_id)))

        # 获取聊天频道信息用于 @ 解析
        db_chat_channel = await DBChatChannel.get_channel(chat_key=request.chat_key)

        for segment in request.segments:
            if segment.type == PlatformSendSegmentType.TEXT:
                if segment.content.strip():
                    # NoneBot 特有功能：解析文本中的 @ 信息
                    seg_data = await parse_at_from_text(segment.content, db_chat_channel)

                    for seg in seg_data:
                        if isinstance(seg, str):
                            if seg.strip():
                                message.append(MessageSegment.text(seg))
                        elif isinstance(seg, SegAt):  # SegAt 对象
                            message.append(MessageSegment.at(user_id=seg.platform_user_id))

            elif segment.type == PlatformSendSegmentType.AT:
                if segment.at_info:
                    message.append(MessageSegment.at(user_id=segment.at_info.platform_user_id))
            elif segment.type == PlatformSendSegmentType.IMAGE:
                # 图片以富文本形式发送
                if segment.file_path:
                    file_path = Path(segment.file_path)
                    if file_path.exists():
                        onebot_uri = _resolve_onebot_file_uri(file_path)
                        logger.info(f"OneBot 图片本地路径已规范为 file URI: raw={file_path} uri={onebot_uri}")
                        message.append(MessageSegment.image(file=onebot_uri))
                    else:
                        message.append(MessageSegment.text(f"Image file not found: {segment.file_path}"))
            elif segment.type == PlatformSendSegmentType.VOICE:
                if segment.file_path:
                    file_path = Path(segment.file_path)
                    if file_path.exists():
                        voice_b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
                        message.append(MessageSegment.record(file=f"base64://{voice_b64}"))
                    else:
                        message.append(MessageSegment.text(f"Voice file not found: {segment.file_path}"))
            else:
                logger.warning(f"Unsupported segment type in normal mode: {segment.type}")

        if message:
            return await self._send_to_chat(request.chat_key, message)
        return None

    async def _send_files(self, chat_key: str, file_segments: List) -> None:
        """发送文件（文件上传模式）"""
        bot: Bot = get_bot()
        files: List[Path] = []

        # 收集所有文件路径
        for segment in file_segments:
            if segment.file_path:
                file_path = Path(segment.file_path)
                if file_path.exists():
                    files.append(file_path)
                else:
                    logger.warning(f"File not found: {segment.file_path}")

        if not files:
            logger.warning("No valid files to send")
            return

        # 获取聊天频道信息
        db_chat_channel = await DBChatChannel.get_channel(chat_key=chat_key)
        chat_type = db_chat_channel.chat_type

        # 如果配置了 OneBot 服务器挂载目录，需要转换路径
        def get_onebot_path(file_path: Path) -> Path:
            return _resolve_onebot_file_path(file_path)

        if chat_type is ChatType.GROUP:
            chat_id = self._resolve_group_id(db_chat_channel.channel_id)
            for file in files:
                onebot_path = get_onebot_path(file)
                logger.info(f"OneBot 文件上传路径已解析: raw={file} resolved={onebot_path}")
                await bot.upload_group_file(
                    group_id=chat_id,
                    file=str(onebot_path),
                    name=file.name,
                )
        elif chat_type is ChatType.PRIVATE:
            chat_id = self._resolve_private_user_id(db_chat_channel.channel_id)
            for file in files:
                onebot_path = get_onebot_path(file)
                logger.info(f"OneBot 文件上传路径已解析: raw={file} resolved={onebot_path}")
                await bot.upload_private_file(
                    user_id=chat_id,
                    file=str(onebot_path),
                    name=file.name,
                )
        else:
            raise ValueError("Invalid chat type")

    async def _send_to_chat(self, chat_key: str, message: Message) -> str:
        """发送消息到指定聊天"""
        bot: Bot = get_bot()

        # 获取聊天频道信息
        db_chat_channel = await DBChatChannel.get_channel(chat_key=chat_key)
        chat_type = db_chat_channel.chat_type

        try:
            if chat_type is ChatType.GROUP:
                chat_id = self._resolve_group_id(db_chat_channel.channel_id)
                ret = await bot.send_group_msg(group_id=chat_id, message=message)
            elif chat_type is ChatType.PRIVATE:
                chat_id = self._resolve_private_user_id(db_chat_channel.channel_id)
                ret = await bot.send_private_msg(user_id=chat_id, message=message)
            else:
                raise ValueError("Invalid chat type")
        except Exception as e:
            # NapCat 常见现象：发送成功但“消息回执事件”超时，抛 ActionFailed(retcode=1200)；
            # 其 message/wording 里会带 EventRet: {"result": 0}。
            # 这种情况下不应该阻断业务流程（否则工具看似失败，但实际上可能已发送）。
            s = f"{getattr(e, 'message', '')}\n{getattr(e, 'wording', '')}\n{e}"
            if ("retcode=1200" in s or "retcode: 1200" in s or int(getattr(e, "retcode", 0) or 0) == 1200) and (
                "timeout" in s.lower()
            ) and re.search(r"\"result\"\s*:\s*0\b", s):
                logger.warning(f"NapCat sendMsg 回执超时但 result=0，按成功处理: {e}")
                return ""
            raise

        logger.debug(f"发送消息成功: {ret}")
        return str(ret.get("message_id", "")) or ""

    def _resolve_group_id(self, channel_id: str) -> int:
        raw = str(channel_id or "").strip()
        if not raw.startswith("group_"):
            raise ValueError(f"OneBot 群聊 channel_id 非法: {channel_id}")
        return int(raw.split("_", 1)[1])

    def _resolve_private_user_id(self, channel_id: str) -> int:
        raw = str(channel_id or "").strip()
        if not raw.startswith("private_"):
            raise ValueError(f"OneBot 私聊 channel_id 非法: {channel_id}")
        target_user_id = raw.split("_", 1)[1]
        canonical_private = f"private_{get_primary_advanced_user_id()}"
        if raw == canonical_private:
            owner_uid = str(getattr(self.config, "OWNER_QQ_USER_ID", "") or "").strip()
            if not owner_uid:
                raise ValueError("OneBot 高级私聊出站需要配置 OWNER_QQ_USER_ID")
            logger.info(
                "OneBot 高级私聊出站回映射: canonical_channel=%s owner_qq=%s",
                raw,
                owner_uid,
            )
            target_user_id = owner_uid
        return int(target_user_id)

    async def get_self_info(self) -> PlatformUser:
        """获取自身信息"""
        bot: Bot = get_bot()
        if bot:
            logger.info(f"Self_id:{bot.self_id} user_name:{bot.self_id}")
            return PlatformUser(platform_name="QQ", user_id=str(bot.self_id), user_name=bot.self_id)
        raise ValueError("No bot found")

    async def get_user_info(self, user_id: str, channel_id: str) -> PlatformUser:
        """获取用户(或者群聊用户)信息"""
        raise NotImplementedError

    async def get_channel_info(self, channel_id: str) -> PlatformChannel:
        """获取频道信息"""
        chat_type = get_channel_type(channel_id)
        if chat_type == ChatType.GROUP:
            try:
                channel_name = (await get_bot().get_group_info(group_id=self._resolve_group_id(channel_id)))["group_name"]
            except Exception as e:
                logger.error(f"获取群组名称失败: {e!s}")
                channel_name = channel_id
        elif chat_type == ChatType.PRIVATE:
            channel_name = (await get_bot().get_stranger_info(user_id=self._resolve_private_user_id(channel_id)))["nickname"]
        else:
            channel_name = channel_id

        return PlatformChannel(channel_id=channel_id, channel_name=channel_name, channel_type=chat_type)

    async def set_message_reaction(self, message_id: str, status: bool = True) -> bool:
        """设置消息反应（NoneBot 实现）

        Args:
            message_id (str): 消息ID
            status (bool): True为设置反应，False为取消反应

        Returns:
            bool: 是否成功设置
        """
        try:
            bot: Bot = get_bot()
            await bot.call_api(
                "set_msg_emoji_like",
                message_id=int(message_id),
                emoji_id="212",
                set="true" if status else "false",
            )
        except Exception as e:
            logger.error(f"设置消息emoji失败: {e} | 如果协议端不支持该功能，请关闭配置 `SESSION_PROCESSING_WITH_EMOJI`")
            return False
        else:
            return True
