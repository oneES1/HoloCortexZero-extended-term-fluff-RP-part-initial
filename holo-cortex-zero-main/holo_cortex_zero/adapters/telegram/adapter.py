"""
Telegram 适配器实现
"""

import asyncio
import contextlib
import mimetypes
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, List, Optional, Tuple

from telegram import Bot
from telegram.ext import Application, MessageHandler, filters
from telegram.request import HTTPXRequest

from holo_cortex_zero.adapters.interface.base import AdapterMetadata, BaseAdapter
from holo_cortex_zero.adapters.interface.schemas.platform import (
    ChatType,
    PlatformChannel,
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformSendSegmentType,
    PlatformUser,
)
from holo_cortex_zero.core import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.runtime_identity import get_primary_advanced_user_id

from .config import TelegramConfig
from .message_processor import MessageProcessor

try:
    import magic  # type: ignore
except Exception:  # pragma: no cover
    magic = None

if TYPE_CHECKING:
    from fastapi import APIRouter


class TelegramAdapter(BaseAdapter[TelegramConfig]):
    """基于 python-telegram-bot 的 Telegram 适配器"""

    def __init__(self, config_cls: type[TelegramConfig] = TelegramConfig):
        super().__init__(config_cls)
        self.application: Optional[Application] = None
        self.message_processor: Optional[MessageProcessor] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._polling_retries = 0
        self._max_polling_retries = 5
        self._polling_retry_delay = 5  # 秒
        self._self_info_cache: Optional[PlatformUser] = None

    @staticmethod
    def _normalize_proxy_url(proxy_url: str) -> str:
        url = str(proxy_url or "").strip()
        lower_url = url.lower()
        if lower_url.startswith("socks5h://"):
            return f"socks5://{url[len('socks5h://') :]}"
        if lower_url.startswith("socks://"):
            return f"socks5://{url[len('socks://') :]}"
        return url

    def _effective_proxy_url(self) -> tuple[Optional[str], str]:
        config_proxy = str(getattr(self.config, "PROXY_URL", "") or "").strip()
        if config_proxy:
            return self._normalize_proxy_url(config_proxy), "config"

        return None, "none"

    def _build_httpx_request(self, *, proxy_url: Optional[str], read_timeout: float) -> HTTPXRequest:
        httpx_kwargs = {"trust_env": False}
        return HTTPXRequest(
            connect_timeout=10.0,
            read_timeout=read_timeout,
            write_timeout=10.0,
            pool_timeout=5.0,
            proxy=proxy_url,
            httpx_kwargs=httpx_kwargs,
        )

    @property
    def key(self) -> str:
        return "telegram"

    @property
    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            name="Telegram",
            description="基于 python-telegram-bot 的 Telegram 适配器",
            version="2.0.0",
            author="holo-cortex-zero",
            tags=["telegram", "chat", "bot"],
        )

    @property
    def chat_key_rules(self) -> List[str]:
        return [
            "群聊: `telegram-group_-123456789` (负数为超级群组)",
            "私聊: `telegram-private_123456789` (正数为私聊用户)",
        ]

    def get_primary_advanced_platform_user_ids(self) -> set[str]:
        uid = str(getattr(self.config, "OWNER_TG_USER_ID", "") or "").strip()
        return {uid} if uid else set()

    def build_chat_key(self, chat_id_or_chat) -> str:
        """重写基类方法，生成包含类型前缀的聊天标识
        
        Args:
            chat_id_or_chat: 可以是 chat.id (int) 或 Chat 对象
        
        Returns:
            str: 完整的聊天标识，格式为 telegram-{type}_{id}
        """
        # Chat 对象
        if hasattr(chat_id_or_chat, "type") and hasattr(chat_id_or_chat, "id"):
            chat_type = str(getattr(chat_id_or_chat, "type", "") or "")
            chat_id = int(getattr(chat_id_or_chat, "id"))
            normalized_type = "private" if chat_type == "private" else "group"
            return f"{self.key}-{normalized_type}_{chat_id}"

        # 纯 chat_id（默认按私聊处理）
        try:
            chat_id = int(chat_id_or_chat)
        except Exception:
            return super().build_chat_key(str(chat_id_or_chat))

        return f"{self.key}-private_{chat_id}"

    def parse_chat_key(self, chat_key: str) -> Tuple[str, str]:
        """解析聊天标识（Telegram 特殊处理负数群组ID）

        Args:
            chat_key: 聊天标识，格式如 telegram-group_-1002768666191

        Returns:
            Tuple[str, str]: (adapter_key, channel_id)

        Raises:
            ValueError: 当聊天标识格式无效时
        """
        # 使用限制分割次数的方式处理，只在第一个 '-' 处分割
        # 这样可以正确处理负数群组ID，如: telegram-group_-1002768666191
        parts = chat_key.split("-", 1)

        if len(parts) != 2:
            raise ValueError(f"无效的聊天标识: {chat_key}")

        adapter_key = parts[0]
        channel_id = parts[1]

        return adapter_key, channel_id

    def _resolve_send_chat_id(self, chat_key: str) -> int:
        """把框架 chat_key 解析为 Telegram 真实 chat_id（含高级私聊回映射）。"""
        _, channel_id = self.parse_chat_key(chat_key)
        chat_id = int(channel_id.split("_", 1)[1]) if "_" in channel_id else int(channel_id)

        # 主干回映射：框架高级私聊 private_<ADVANCED_USER_ID> -> TG owner chat_id。
        try:
            owner_uid = str(getattr(self.config, "OWNER_TG_USER_ID", "") or "").strip()
            canonical_uid = get_primary_advanced_user_id(config)
            if owner_uid.isdigit() and str(channel_id) == f"private_{canonical_uid}":
                chat_id = int(owner_uid)
        except Exception:
            pass

        return chat_id

    @staticmethod
    def _send_timeout_kwargs() -> dict[str, float]:
        return {
            "connect_timeout": 2.0,
            "read_timeout": 3.0,
            "write_timeout": 5.0,
            "pool_timeout": 1.0,
        }

    @staticmethod
    def _is_transient_send_error(error: Exception) -> bool:
        err_text = str(error).lower()
        err_cls = error.__class__.__name__.lower()
        transient_hints = (
            "timed out",
            "timeout",
            "network",
            "connection reset",
            "temporarily unavailable",
        )
        return any(hint in err_text or hint in err_cls for hint in transient_hints)

    async def _send_with_retry(
        self,
        send_call: Callable[[], Awaitable[Any]],
        *,
        chat_key: str,
        segment_type: str,
        segment_len: int,
        max_attempts: int = 2,
        retry_delay_seconds: float = 0.2,
    ) -> Any:
        for attempt in range(1, max_attempts + 1):
            is_retry = attempt > 1
            started_at = time.monotonic()
            try:
                result = await send_call()
                elapsed_ms = (time.monotonic() - started_at) * 1000.0
                logger.info(
                    f"[telegram_send] segment_type={segment_type} segment_len={segment_len} "
                    f"attempt={attempt} is_retry={is_retry} elapsed_ms={elapsed_ms:.1f} "
                    f"error_class=none",
                )
                return result
            except Exception as error:
                elapsed_ms = (time.monotonic() - started_at) * 1000.0
                error_class = error.__class__.__name__
                logger.warning(
                    f"[telegram_send] segment_type={segment_type} segment_len={segment_len} "
                    f"attempt={attempt} is_retry={is_retry} elapsed_ms={elapsed_ms:.1f} "
                    f"error_class={error_class}",
                )
                if attempt >= max_attempts or not self._is_transient_send_error(error):
                    raise
                await asyncio.sleep(retry_delay_seconds)

        raise RuntimeError("Telegram 发送重试逻辑异常结束")

    async def init(self) -> None:
        """初始化适配器"""
        if not self.config.BOT_TOKEN:
            logger.warning("BOT_TOKEN 未配置，跳过 Telegram 适配器初始化")
            return

        proxy_url, proxy_source = self._effective_proxy_url()
        init_attempts = 3

        for attempt in range(1, init_attempts + 1):
            application: Optional[Application] = None
            try:
                logger.info(
                    f"Telegram 适配器初始化 attempt={attempt}/{init_attempts} proxy_source={proxy_source}"
                )
                builder = Application.builder().token(self.config.BOT_TOKEN)
                builder = builder.request(self._build_httpx_request(proxy_url=proxy_url, read_timeout=20.0))
                builder = builder.get_updates_request(self._build_httpx_request(proxy_url=proxy_url, read_timeout=35.0))
                application = builder.build()

                message_processor = MessageProcessor(self)
                application.add_handler(
                    MessageHandler(filters.ALL, message_processor.process_update),
                )

                await application.initialize()
                await application.start()

                self.application = application
                self.message_processor = message_processor
                self._polling_retries = 0
                self._polling_task = asyncio.create_task(self._start_polling_with_retry())

                logger.info("Telegram 适配器初始化成功")
                return

            except Exception as e:
                logger.error(f"Telegram 适配器初始化失败 attempt={attempt}/{init_attempts}: {e.__class__.__name__}")
                if application is not None:
                    with contextlib.suppress(Exception):
                        if application.updater:
                            await application.updater.stop()
                    with contextlib.suppress(Exception):
                        await application.stop()
                    with contextlib.suppress(Exception):
                        await application.shutdown()

                if attempt < init_attempts:
                    await asyncio.sleep(2)

        self.application = None
        self.message_processor = None

    async def _start_polling(self) -> None:
        """启动轮询"""
        try:
            if self.application and self.application.updater:
                await self.application.updater.start_polling()
                logger.info("Telegram 轮询已启动")
                # 成功启动后重置重试计数
                self._polling_retries = 0
        except Exception as e:
            logger.error(f"Telegram 轮询启动失败: {e.__class__.__name__}")
            raise

    async def _start_polling_with_retry(self) -> None:
        """启动带重试机制的轮询"""
        while self._polling_retries < self._max_polling_retries:
            try:
                await self._start_polling()
                return  # 成功启动，退出循环
            except Exception as e:
                self._polling_retries += 1
                if self._polling_retries < self._max_polling_retries:
                    logger.warning(
                        f"Telegram 轮询启动失败，第 {self._polling_retries} 次重试，"
                        f"{self._polling_retry_delay} 秒后重试: {e.__class__.__name__}"
                    )
                    await asyncio.sleep(self._polling_retry_delay)
                else:
                    logger.error(
                        f"Telegram 轮询启动失败，已达到最大重试次数 {self._max_polling_retries}，"
                        f"请检查网络连接或 Bot Token 配置"
                    )
                    break

    async def cleanup(self) -> None:
        """清理适配器"""
        try:
            # 停止轮询任务
            if self._polling_task and not self._polling_task.done():
                self._polling_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._polling_task

            # 停止应用
            if self.application:
                if self.application.updater:
                    await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()

            self._self_info_cache = None


            logger.info("Telegram 适配器已清理")
        except Exception as e:
            logger.error(f"Telegram 适配器清理失败: {e.__class__.__name__}")

    async def forward_message(
        self,
        request: PlatformSendRequest,
    ) -> PlatformSendResponse:
        """转发消息到 Telegram 平台"""
        if not self.application or not self.application.bot:
            return PlatformSendResponse(
                success=False,
                error_message="Telegram 适配器未初始化",
            )

        try:
            chat_id = self._resolve_send_chat_id(request.chat_key)

            message_ids = []
            bot = self.application.bot

            text_segments = [
                seg for seg in request.segments
                if seg.type == PlatformSendSegmentType.TEXT and str(seg.content or "").strip()
            ]
            media_segments = [
                seg for seg in request.segments
                if seg.type in {PlatformSendSegmentType.IMAGE, PlatformSendSegmentType.FILE}
                and seg.file_path
                and Path(seg.file_path).exists()
            ]
            other_segments = [
                seg for seg in request.segments
                if seg.type not in {PlatformSendSegmentType.TEXT, PlatformSendSegmentType.IMAGE, PlatformSendSegmentType.FILE}
            ]

            if len(media_segments) == 1 and not other_segments:
                media_segment = media_segments[0]
                media_path = Path(str(media_segment.file_path))
                caption = "\n".join(str(seg.content or "").strip() for seg in text_segments if str(seg.content or "").strip())
                mime_type = ""
                try:
                    if magic is not None:
                        mime_type = str(magic.from_file(str(media_path), mime=True) or "").strip()
                except Exception:
                    mime_type = ""
                mime_type = mime_type or mimetypes.guess_type(str(media_path))[0] or "application/octet-stream"

                if media_segment.type == PlatformSendSegmentType.IMAGE:
                    try:
                        if mime_type == "image/gif":
                            message = await self._send_with_retry(
                                lambda file_path=str(media_path), content=caption: bot.send_animation(
                                    chat_id=chat_id,
                                    animation=file_path,
                                    caption=content or None,
                                    reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                                    **self._send_timeout_kwargs(),
                                ),
                                chat_key=request.chat_key,
                                segment_type=PlatformSendSegmentType.IMAGE.value,
                                segment_len=len(str(media_path)),
                            )
                        else:
                            message = await self._send_with_retry(
                                lambda file_path=str(media_path), content=caption: bot.send_photo(
                                    chat_id=chat_id,
                                    photo=file_path,
                                    caption=content or None,
                                    reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                                    **self._send_timeout_kwargs(),
                                ),
                                chat_key=request.chat_key,
                                segment_type=PlatformSendSegmentType.IMAGE.value,
                                segment_len=len(str(media_path)),
                            )
                        return PlatformSendResponse(success=True, message_id=str(message.message_id))
                    except Exception:
                        message = await self._send_with_retry(
                            lambda file_path=str(media_path), content=caption: bot.send_document(
                                chat_id=chat_id,
                                document=file_path,
                                caption=content or None,
                                reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                                **self._send_timeout_kwargs(),
                            ),
                            chat_key=request.chat_key,
                            segment_type=PlatformSendSegmentType.FILE.value,
                            segment_len=len(str(media_path)),
                        )
                        return PlatformSendResponse(success=True, message_id=str(message.message_id))

                message = await self._send_with_retry(
                    lambda file_path=str(media_path), content=caption: bot.send_document(
                        chat_id=chat_id,
                        document=file_path,
                        caption=content or None,
                        reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                        **self._send_timeout_kwargs(),
                    ),
                    chat_key=request.chat_key,
                    segment_type=PlatformSendSegmentType.FILE.value,
                    segment_len=len(str(media_path)),
                )
                return PlatformSendResponse(success=True, message_id=str(message.message_id))

            # 处理消息段
            for segment in request.segments:
                if segment.type == PlatformSendSegmentType.TEXT:
                    if segment.content and segment.content.strip():
                        message = await self._send_with_retry(
                            lambda content=segment.content: bot.send_message(
                                chat_id=chat_id,
                                text=content,
                                reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                                **self._send_timeout_kwargs(),
                            ),
                            chat_key=request.chat_key,
                            segment_type=PlatformSendSegmentType.TEXT.value,
                            segment_len=len(segment.content or ""),
                        )
                        message_ids.append(str(message.message_id))

                elif segment.type == PlatformSendSegmentType.AT:
                    # Telegram @ 功能通过在文本中包含 @username 或用户ID来实现
                    # 这里将 AT 段转换为文本形式
                    if segment.at_info:
                        at_text = f"@{segment.at_info.nickname or segment.at_info.platform_user_id}"
                        message = await self._send_with_retry(
                            lambda at_content=at_text: bot.send_message(
                                chat_id=chat_id,
                                text=at_content,
                                reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                                **self._send_timeout_kwargs(),
                            ),
                            chat_key=request.chat_key,
                            segment_type=PlatformSendSegmentType.AT.value,
                            segment_len=len(at_text),
                        )
                        message_ids.append(str(message.message_id))

                elif segment.type == PlatformSendSegmentType.IMAGE:
                    if segment.file_path and Path(segment.file_path).exists():
                        message = await self._send_with_retry(
                            lambda file_path=segment.file_path: bot.send_photo(
                                chat_id=chat_id,
                                photo=str(file_path),
                                reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                                **self._send_timeout_kwargs(),
                            ),
                            chat_key=request.chat_key,
                            segment_type=PlatformSendSegmentType.IMAGE.value,
                            segment_len=len(str(segment.file_path or "")),
                        )
                        message_ids.append(str(message.message_id))

                elif (
                    segment.type == PlatformSendSegmentType.VOICE
                    and segment.file_path
                    and Path(segment.file_path).exists()
                ):
                    try:
                        message = await self._send_with_retry(
                            lambda file_path=segment.file_path: bot.send_voice(
                                chat_id=chat_id,
                                voice=str(file_path),
                                reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                                **self._send_timeout_kwargs(),
                            ),
                            chat_key=request.chat_key,
                            segment_type=PlatformSendSegmentType.VOICE.value,
                            segment_len=len(str(segment.file_path or "")),
                        )
                    except Exception:
                        message = await self._send_with_retry(
                            lambda file_path=segment.file_path: bot.send_audio(
                                chat_id=chat_id,
                                audio=str(file_path),
                                reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                                **self._send_timeout_kwargs(),
                            ),
                            chat_key=request.chat_key,
                            segment_type=PlatformSendSegmentType.VOICE.value,
                            segment_len=len(str(segment.file_path or "")),
                        )
                    message_ids.append(str(message.message_id))

                elif (
                    segment.type == PlatformSendSegmentType.FILE
                    and segment.file_path
                    and Path(segment.file_path).exists()
                ):
                    message = await self._send_with_retry(
                        lambda file_path=segment.file_path: bot.send_document(
                            chat_id=chat_id,
                            document=str(file_path),
                            reply_to_message_id=int(request.ref_msg_id) if request.ref_msg_id else None,
                            **self._send_timeout_kwargs(),
                        ),
                        chat_key=request.chat_key,
                        segment_type=PlatformSendSegmentType.FILE.value,
                        segment_len=len(str(segment.file_path or "")),
                    )
                    message_ids.append(str(message.message_id))

            if message_ids:
                return PlatformSendResponse(
                    success=True,
                    message_id=message_ids[0]
                    if len(message_ids) == 1
                    else ",".join(message_ids),
                )
            return PlatformSendResponse(
                success=True,
                message_id="empty",
            )

        except Exception as e:
            logger.error(f"Telegram 消息发送失败: {e.__class__.__name__}")
            return PlatformSendResponse(success=False, error_message="Telegram 消息发送失败")

    async def edit_message(self, chat_key: str, message_id: str, text: str) -> PlatformSendResponse:
        """编辑已发送消息（用于流式可见输出）"""
        if not self.application or not self.application.bot:
            return PlatformSendResponse(success=False, error_message="Telegram 适配器未初始化")

        bot = self.application.bot
        chat_id = self._resolve_send_chat_id(chat_key)

        # Telegram 对 message_id 要求整型
        try:
            msg_id = int(str(message_id).split(",")[0])
        except Exception:
            return PlatformSendResponse(success=False, error_message="无效的 message_id")

        try:
            msg = await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text or "…",
            )
            return PlatformSendResponse(success=True, message_id=str(getattr(msg, "message_id", msg_id)))
        except Exception as e:
            err_text = str(e)
            err_lower = err_text.lower()

            # 目标文本与当前一致，不视为失败
            if "message is not modified" in err_lower:
                return PlatformSendResponse(success=True, message_id=str(msg_id))

            # Telegram 频控：按 retry_after 一次退避重试
            retry_after = getattr(e, "retry_after", None)
            if retry_after:
                try:
                    await asyncio.sleep(float(retry_after))
                    msg = await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=text or "…",
                    )
                    return PlatformSendResponse(success=True, message_id=str(getattr(msg, "message_id", msg_id)))
                except Exception:
                    return PlatformSendResponse(success=False, error_message="Telegram 编辑消息失败(重试后)")

            return PlatformSendResponse(success=False, error_message="Telegram 编辑消息失败")

    async def delete_message(self, chat_key: str, message_id: str) -> bool:
        """删除已发送消息（用于流式占位清理）"""
        if not self.application or not self.application.bot:
            return False

        try:
            chat_id = self._resolve_send_chat_id(chat_key)
            msg_id = int(str(message_id).split(",")[0])
            await self.application.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            return True
        except Exception:
            return False

    async def get_self_info(self) -> PlatformUser:
        """获取自身信息"""
        # TG Bot 身份在进程生命周期内基本稳定，做常驻缓存避免每轮都 get_me()
        if self._self_info_cache:
            return self._self_info_cache

        if not self.application or not self.application.bot:
            raise RuntimeError("Telegram 适配器未初始化")

        bot_info = await self.application.bot.get_me()

        self._self_info_cache = PlatformUser(
            platform_name=self.key,
            user_id=str(bot_info.id),
            user_name=bot_info.username or "",
            user_avatar="",
        )
        return self._self_info_cache

    async def get_user_info(self, user_id: str, channel_id: str) -> PlatformUser:
        """获取用户信息
        
        注意：这个方法主要用于其他地方需要获取用户信息时调用
        在消息处理过程中，应直接使用 message.from_user 中的信息
        """
        if not self.application or not self.application.bot:
            raise RuntimeError("Telegram 适配器未初始化")

        try:
            chat_id = int(channel_id.split("_", 1)[1]) if "_" in channel_id else int(channel_id)

            # 主干回映射：框架高级私聊 private_<ADVANCED_USER_ID> -> TG owner。
            try:
                owner_uid = str(getattr(self.config, "OWNER_TG_USER_ID", "") or "").strip()
                canonical_uid = get_primary_advanced_user_id(config)
                if owner_uid.isdigit() and str(channel_id) == f"private_{canonical_uid}":
                    chat_id = int(owner_uid)
                    user_id = str(owner_uid)
            except Exception:
                pass
            bot = self.application.bot

            # 对于群聊，尝试获取群成员信息
            if "group" in channel_id:
                member = await bot.get_chat_member(chat_id, int(user_id))
                user = member.user
            else:
                # 对于私聊，无法获取详细信息，只能返回基本信息
                # 返回默认用户信息
                return PlatformUser(
                    platform_name=self.key,
                    user_id=user_id,
                    user_name=user_id,
                    user_avatar="",
                )

            # 构建完整的用户名称
            first_name = user.first_name or ""
            last_name = user.last_name or ""
            username = user.username or ""
            
            # 优先使用完整名称，然后是用户名
            if first_name and last_name:
                display_name = f"{first_name} {last_name}"
            elif first_name:
                display_name = first_name
            elif username:
                display_name = username
            else:
                display_name = str(user.id)

            return PlatformUser(
                platform_name=self.key,
                user_id=str(user.id),
                user_name=display_name,
                user_avatar="",
            )
        except Exception as e:
            logger.error(f"获取用户信息失败: {e.__class__.__name__}")
            # 返回默认用户信息
            return PlatformUser(
                platform_name=self.key,
                user_id=user_id,
                user_name=user_id,
                user_avatar="",
            )

    async def get_channel_info(self, channel_id: str) -> PlatformChannel:
        """获取频道信息"""
        if not self.application or not self.application.bot:
            raise RuntimeError("Telegram 适配器未初始化")

        try:
            chat_id = int(channel_id.split("_", 1)[1]) if "_" in channel_id else int(channel_id)

            # 主干回映射：框架高级私聊 private_<ADVANCED_USER_ID> -> TG owner。
            try:
                owner_uid = str(getattr(self.config, "OWNER_TG_USER_ID", "") or "").strip()
                canonical_uid = get_primary_advanced_user_id(config)
                if owner_uid.isdigit() and str(channel_id) == f"private_{canonical_uid}":
                    chat_id = int(owner_uid)
            except Exception:
                pass
            bot = self.application.bot

            chat = await bot.get_chat(chat_id)

            chat_type = (
                ChatType.PRIVATE
                if chat.type.value == "private"
                else ChatType.GROUP
            )

            return PlatformChannel(
                platform_name=self.key,
                channel_id=channel_id,
                channel_name=chat.title or chat.first_name or str(chat_id),
                channel_type=chat_type,
            )
        except Exception as e:
            logger.error(f"获取频道信息失败: {e.__class__.__name__}")
            # 返回默认频道信息
            chat_type = ChatType.PRIVATE if "private" in channel_id else ChatType.GROUP
            return PlatformChannel(
                platform_name=self.key,
                channel_id=channel_id,
                channel_name=channel_id,
                channel_type=chat_type,
            )

    def get_adapter_router(self) -> "APIRouter":
        """获取适配器路由"""
        from .routers import router

        return router
