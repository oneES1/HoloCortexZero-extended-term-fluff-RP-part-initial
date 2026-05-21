"""
Telegram 消息处理器
"""

import asyncio
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Any, Dict, Tuple

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

from telegram import Update, Message, Document, PhotoSize, Video, Audio, Voice, VideoNote, Sticker
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from holo_cortex_zero.adapters.telegram.adapter import TelegramAdapter

from holo_cortex_zero.adapters.interface.schemas.platform import (
    PlatformChannel,
    PlatformMessage,
    PlatformUser,
    ChatType,
)
from holo_cortex_zero.adapters.interface.schemas.extra import PlatformMessageExt
from holo_cortex_zero.adapters.interface.identity import preview_canonical_inbound_identity
from holo_cortex_zero.core import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.services.file_system.policy import resolve_incoming_attachment_mode
from holo_cortex_zero.schemas.chat_message import (
    ChatMessageSegment,
    ChatMessageSegmentType,
    ChatMessageSegmentImage,
    ChatMessageSegmentFile,
    ChatMessageSegmentAt,
    build_reference_segment,
    extract_primary_reference_segment,
)
from holo_cortex_zero.tools.common_util import download_file_from_bytes


class MessageProcessor:
    """消息处理器"""

    def __init__(self, adapter: "TelegramAdapter"):
        self.adapter = adapter

    async def process_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 Telegram 更新"""
        try:
            if update.message:
                await self._handle_message(update.message, context)
            elif update.edited_message:
                await self._handle_edited_message(update.edited_message, context)
            # 可以添加更多类型的处理，如 inline_query, callback_query 等
        except Exception as e:
            logger.error(f"处理 Telegram 更新时出错: {e}")

    async def _handle_message(self, message: Message, context: ContextTypes.DEFAULT_TYPE = None) -> None:
        """处理消息"""
        if not message.from_user:
            return
        if message.chat.type == "private" and not self.adapter.config.AUTO_ACCEPT_PRIVATE_CHAT:
            logger.info(
                f"Telegram 私聊 update 未接入: chat_id={message.chat.id} user_id={message.from_user.id} "
                "reason=private_chat_disabled"
            )
            return

        # 获取用户真实昵称和显示名称
        user_display_name, user_nickname = await self._get_user_display_info(
            message.from_user, message.chat
        )

        raw_user_id, raw_sender_name, raw_sender_nickname = self._get_effective_sender_profile(
            message,
            user_display_name,
            user_nickname,
        )

        # 构造平台用户信息
        platform_user = PlatformUser(
            platform_name=self.adapter.key,
            user_id=raw_user_id,
            user_name=raw_sender_name,
            user_avatar="",
        )

        # 获取频道显示名称
        channel_display_name = await self._get_channel_display_name(message.chat)

        # 构造平台频道信息
        chat_type = ChatType.PRIVATE if message.chat.type == "private" else ChatType.GROUP
        platform_channel = PlatformChannel(
            platform_name=self.adapter.key,
            channel_id=f"{chat_type.value}_{message.chat.id}",
            channel_name=channel_display_name,
            channel_type=chat_type,
        )

        # 处理消息内容
        content_segments = await self._process_message_content(message)
        
        # 构造平台消息
        platform_message = PlatformMessage(
            message_id=str(message.message_id),
            sender_id=raw_user_id,
            sender_name=raw_sender_name,
            content_text=self._extract_text_content(content_segments),
            content_data=content_segments,
            sender_nickname=raw_sender_nickname,
            is_self=message.from_user.id == context.bot.id if context and context.bot else False,
            is_tome=self._is_mentioned(message, context),
            ext_data=self._build_reference_ext(content_segments, self.adapter.build_chat_key(message.chat)),
        )
        if platform_message.ext_data:
            platform_message.ext_data.native_voice = bool(message.voice)

        # 收集消息
        from holo_cortex_zero.adapters.interface.collector import collect_message
        await collect_message(
            self.adapter,
            platform_channel,
            platform_user,
            platform_message,
            trigger_agent=bool(message.voice),
        )

    async def _handle_edited_message(self, message: Message, context: ContextTypes.DEFAULT_TYPE = None) -> None:
        """处理编辑消息"""
        # 目前简单处理为新消息
        await self._handle_message(message, context)

    async def _process_message_content(self, message: Message, *, include_reference: bool = True) -> List[ChatMessageSegment]:
        """处理消息内容，转换为标准消息段"""
        segments: List[ChatMessageSegment] = []
        chat_key, effective_sender_id = self._preview_canonical_attachment_identity(message)

        if include_reference and message.reply_to_message:
            reference_segment = await self._build_reference_segment_from_message(message.reply_to_message)
            if reference_segment:
                segments.append(reference_segment)

        # 处理文本内容
        text_content = message.text or message.caption
        if text_content:
            segment = ChatMessageSegment(type=ChatMessageSegmentType.TEXT, text=text_content)
            segments.append(segment)

        # 处理照片
        if message.photo:
            # 选择最大尺寸的照片
            largest_photo = max(message.photo, key=lambda p: p.file_size or 0)
            photo_bytes = await self._download_file_bytes(largest_photo.file_id)
            if photo_bytes:
                # 智能检测文件类型
                mime_type, extension = self._detect_file_type_and_extension(photo_bytes)
                safe_id = self._sanitize_filename(largest_photo.file_id)
                filename = f"photo_{safe_id}{extension or '.jpg'}"
                attachment_ingest_mode, attachment_reason = resolve_incoming_attachment_mode(
                    adapter_key=self.adapter.key,
                    chat_key=chat_key,
                    chat_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                    sender_id=effective_sender_id,
                    platform_userid=effective_sender_id,
                    attachment_kind="image",
                    channel_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                )
                logger.info(
                    f"Telegram 附件接收策略: chat_key={chat_key} sender={effective_sender_id} kind=image mode={attachment_ingest_mode} reason={attachment_reason}",
                )
                
                segment = await ChatMessageSegmentImage.create_from_bytes(
                    photo_bytes,
                    from_chat_key=chat_key,
                    file_name=filename,
                    ingest_mode=attachment_ingest_mode,
                    mime_type=mime_type,
                )
                segments.append(segment)

        # 处理文档
        if message.document:
            doc_bytes = await self._download_file_bytes(message.document.file_id)
            if doc_bytes:
                # 智能检测文件类型
                mime_type, extension = self._detect_file_type_and_extension(
                    doc_bytes, message.document.file_name
                )
                
                # 构建文件名：
                # - 普通文档尽量保留原始文件名（便于用户识别）
                # - 音视频类文档强制加 file_id 前缀，避免多平台/多会话同名文件导致“读到旧媒体”
                safe_id = self._sanitize_filename(message.document.file_id)
                orig_name = str(message.document.file_name or "")
                orig_ext = ""
                try:
                    if orig_name:
                        orig_ext = Path(orig_name).suffix.lower()
                except Exception:
                    orig_ext = ""
                use_ext = extension or orig_ext or ".bin"
                attachment_kind = "image" if str(mime_type or "").startswith("image/") else "file"
                attachment_ingest_mode, attachment_reason = resolve_incoming_attachment_mode(
                    adapter_key=self.adapter.key,
                    chat_key=chat_key,
                    chat_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                    sender_id=effective_sender_id,
                    platform_userid=effective_sender_id,
                    attachment_kind=attachment_kind,
                    channel_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                )
                logger.info(
                    f"Telegram 附件接收策略: chat_key={chat_key} sender={effective_sender_id} kind={attachment_kind} mode={attachment_ingest_mode} reason={attachment_reason}",
                )
                media_exts = {
                    ".mp3", ".wav", ".ogg", ".oga", ".m4a", ".flac", ".aac", ".opus", ".webm", ".amr", ".silk", ".pcm", ".caf",
                    ".mp4", ".mov", ".mkv", ".avi",
                }
                is_media_doc = str(mime_type or "").lower().startswith(("audio/", "video/")) or (use_ext in media_exts)
                if is_media_doc:
                    filename = f"document_{safe_id}{use_ext}"
                elif orig_name:
                    filename = orig_name
                else:
                    filename = f"document_{safe_id}{use_ext}"
                
                segment = await ChatMessageSegmentFile.create_from_bytes(
                    doc_bytes,
                    from_chat_key=chat_key,
                    file_name=filename,
                    ingest_mode=attachment_ingest_mode,
                    mime_type=mime_type,
                )
                segments.append(segment)

        # 处理视频
        if message.video:
            video_bytes = await self._download_file_bytes(message.video.file_id)
            if video_bytes:
                # 智能检测文件类型
                mime_type, extension = self._detect_file_type_and_extension(video_bytes)
                safe_id = self._sanitize_filename(message.video.file_id)
                filename = f"video_{safe_id}{extension or '.mp4'}"
                attachment_ingest_mode, attachment_reason = resolve_incoming_attachment_mode(
                    adapter_key=self.adapter.key,
                    chat_key=chat_key,
                    chat_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                    sender_id=effective_sender_id,
                    platform_userid=effective_sender_id,
                    attachment_kind="video",
                    channel_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                )
                logger.info(
                    f"Telegram 附件接收策略: chat_key={chat_key} sender={effective_sender_id} kind=video mode={attachment_ingest_mode} reason={attachment_reason}",
                )
                
                segment = await ChatMessageSegmentFile.create_from_bytes(
                    video_bytes,
                    from_chat_key=chat_key,
                    file_name=filename,
                    ingest_mode=attachment_ingest_mode,
                    mime_type=mime_type,
                )
                segments.append(segment)

        # 处理音频
        if message.audio:
            audio_bytes = await self._download_file_bytes(message.audio.file_id)
            if audio_bytes:
                # 智能检测文件类型
                mime_type, extension = self._detect_file_type_and_extension(
                    audio_bytes, message.audio.file_name
                )
                
                # 构建文件名：始终使用 file_id 生成唯一文件名，避免多平台/多会话出现同名文件导致“读到旧音频”
                safe_id = self._sanitize_filename(message.audio.file_id)
                orig_ext = ""
                try:
                    if message.audio.file_name:
                        orig_ext = Path(str(message.audio.file_name)).suffix.lower()
                except Exception:
                    orig_ext = ""
                use_ext = extension or orig_ext or ".mp3"
                filename = f"audio_{safe_id}{use_ext}"
                attachment_ingest_mode, attachment_reason = resolve_incoming_attachment_mode(
                    adapter_key=self.adapter.key,
                    chat_key=chat_key,
                    chat_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                    sender_id=effective_sender_id,
                    platform_userid=effective_sender_id,
                    attachment_kind="audio",
                    channel_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                )
                logger.info(
                    f"Telegram 附件接收策略: chat_key={chat_key} sender={effective_sender_id} kind=audio mode={attachment_ingest_mode} reason={attachment_reason}",
                )
                
                segment = await ChatMessageSegmentFile.create_from_bytes(
                    audio_bytes,
                    from_chat_key=chat_key,
                    file_name=filename,
                    ingest_mode=attachment_ingest_mode,
                    mime_type=mime_type,
                )
                segments.append(segment)

        # 处理语音
        if message.voice:
            voice_bytes = await self._download_file_bytes(message.voice.file_id)
            if voice_bytes:
                # 智能检测文件类型
                mime_type, extension = self._detect_file_type_and_extension(voice_bytes)
                safe_id = self._sanitize_filename(message.voice.file_id)
                filename = f"voice_{safe_id}{extension or '.ogg'}"
                attachment_ingest_mode, attachment_reason = resolve_incoming_attachment_mode(
                    adapter_key=self.adapter.key,
                    chat_key=chat_key,
                    chat_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                    sender_id=effective_sender_id,
                    platform_userid=effective_sender_id,
                    attachment_kind="audio",
                    channel_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                )
                logger.info(
                    f"Telegram 附件接收策略: chat_key={chat_key} sender={effective_sender_id} kind=audio mode={attachment_ingest_mode} reason={attachment_reason}",
                )
                
                segment = await ChatMessageSegmentFile.create_from_bytes(
                    voice_bytes,
                    from_chat_key=chat_key,
                    file_name=filename,
                    ingest_mode=attachment_ingest_mode,
                    mime_type=mime_type,
                )
                segments.append(segment)

        # 处理贴纸
        if message.sticker:
            sticker_bytes = await self._download_file_bytes(message.sticker.file_id)
            if sticker_bytes:
                safe_id = self._sanitize_filename(message.sticker.file_id)
                is_animated = bool(getattr(message.sticker, "is_animated", False))
                is_video = bool(getattr(message.sticker, "is_video", False))

                # 智能检测文件类型
                mime_type, extension = self._detect_file_type_and_extension(sticker_bytes)

                normalized_sticker = await self._normalize_sticker_image(
                    sticker_bytes=sticker_bytes,
                    mime_type=mime_type,
                    extension=extension,
                    is_animated=is_animated,
                    is_video=is_video,
                )
                if normalized_sticker:
                    normalized_bytes, normalized_ext = normalized_sticker
                    filename = f"sticker_{safe_id}{normalized_ext}"
                    attachment_ingest_mode, attachment_reason = resolve_incoming_attachment_mode(
                        adapter_key=self.adapter.key,
                        chat_key=chat_key,
                        chat_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                        sender_id=effective_sender_id,
                        platform_userid=effective_sender_id,
                        attachment_kind="image",
                        channel_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                    )
                    logger.info(
                        f"Telegram 附件接收策略: chat_key={chat_key} sender={effective_sender_id} kind=image mode={attachment_ingest_mode} reason={attachment_reason}",
                    )
                    segment = await ChatMessageSegmentImage.create_from_bytes(
                        normalized_bytes,
                        from_chat_key=chat_key,
                        file_name=filename,
                        ingest_mode=attachment_ingest_mode,
                        mime_type="image/png",
                    )
                else:
                    fallback_ext = extension or (".webm" if is_video else ".tgs" if is_animated else ".webp")
                    filename = f"sticker_{safe_id}{fallback_ext}"
                    attachment_ingest_mode, attachment_reason = resolve_incoming_attachment_mode(
                        adapter_key=self.adapter.key,
                        chat_key=chat_key,
                        chat_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                        sender_id=effective_sender_id,
                        platform_userid=effective_sender_id,
                        attachment_kind="file",
                        channel_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                    )
                    logger.info(
                        f"Telegram 附件接收策略: chat_key={chat_key} sender={effective_sender_id} kind=file mode={attachment_ingest_mode} reason={attachment_reason}",
                    )
                    segment = await ChatMessageSegmentFile.create_from_bytes(
                        sticker_bytes,
                        from_chat_key=chat_key,
                        file_name=filename,
                        ingest_mode=attachment_ingest_mode,
                        mime_type=mime_type,
                    )
                segments.append(segment)

        # 处理视频笔记
        if message.video_note:
            video_note_bytes = await self._download_file_bytes(message.video_note.file_id)
            if video_note_bytes:
                # 智能检测文件类型
                mime_type, extension = self._detect_file_type_and_extension(video_note_bytes)
                safe_id = self._sanitize_filename(message.video_note.file_id)
                filename = f"video_note_{safe_id}{extension or '.mp4'}"
                attachment_ingest_mode, attachment_reason = resolve_incoming_attachment_mode(
                    adapter_key=self.adapter.key,
                    chat_key=chat_key,
                    chat_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                    sender_id=effective_sender_id,
                    platform_userid=effective_sender_id,
                    attachment_kind="video",
                    channel_type=ChatType.PRIVATE.value if message.chat.type == "private" else ChatType.GROUP.value,
                )
                logger.info(
                    f"Telegram 附件接收策略: chat_key={chat_key} sender={effective_sender_id} kind=video mode={attachment_ingest_mode} reason={attachment_reason}",
                )
                
                segment = await ChatMessageSegmentFile.create_from_bytes(
                    video_note_bytes,
                    from_chat_key=chat_key,
                    file_name=filename,
                    ingest_mode=attachment_ingest_mode,
                    mime_type=mime_type,
                )
                segments.append(segment)

        return segments

    def _sanitize_filename(self, file_id: str) -> str:
        """清理文件 ID 用于文件名（移除非法字符）"""
        import re
        # 移除或替换文件名中的非法字符
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', file_id)
        # 限制文件名长度
        return safe_name[:100] if len(safe_name) > 100 else safe_name

    async def _download_file_bytes(self, file_id: str) -> Optional[bytes]:
        """下载文件并返回字节数据"""
        try:
            if not self.adapter.application:
                return None
                
            file = await self.adapter.application.bot.get_file(file_id)
            
            # 直接下载到内存中
            file_bytes = await file.download_as_bytearray()
            return bytes(file_bytes)
        except Exception as e:
            logger.error(f"下载文件失败 {file_id}: {e}")
            return None

    def _detect_file_type_and_extension(self, file_bytes: bytes, original_filename: Optional[str] = None) -> tuple[str, str]:
        """检测文件类型和扩展名
        
        Args:
            file_bytes: 文件字节数据
            original_filename: 原始文件名
            
        Returns:
            tuple[str, str]: (MIME类型, 扩展名)
        """
        mime_type = "application/octet-stream"  # 默认类型
        extension = ""
        
        # 优先使用 magic 库检测
        if HAS_MAGIC and file_bytes:
            try:
                mime_type = magic.from_buffer(file_bytes, mime=True)
                
                # 根据 MIME 类型推断扩展名
                mime_to_ext = {
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/gif": ".gif",
                    "image/webp": ".webp",
                    "video/mp4": ".mp4",
                    "video/avi": ".avi",
                    "video/quicktime": ".mov",
                    "audio/mpeg": ".mp3",
                    "audio/wav": ".wav",
                    "audio/ogg": ".ogg",
                    "audio/mp4": ".m4a",
                    "application/pdf": ".pdf",
                    "application/zip": ".zip",
                    "text/plain": ".txt",
                }
                extension = mime_to_ext.get(mime_type, "")
            except Exception as e:
                logger.debug(f"Magic 库检测文件类型失败: {e}")
        
        # 如果 magic 库未检测出扩展名，尝试从原始文件名获取
        if not extension and original_filename:
            import os
            _, ext = os.path.splitext(original_filename.lower())
            if ext:
                extension = ext
                
        return mime_type, extension

    async def _normalize_sticker_image(
        self,
        sticker_bytes: bytes,
        mime_type: str,
        extension: str,
        is_animated: bool = False,
        is_video: bool = False,
    ) -> Optional[Tuple[bytes, str]]:
        """标准化静态贴纸，确保视觉模型可消费。"""
        normalized_mime = str(mime_type or "").lower()
        normalized_ext = str(extension or "").lower()

        # 常见视觉模型对 webp/tgs 支持不稳定，统一转为 PNG
        if normalized_mime in {"image/png", "image/jpeg", "image/gif"}:
            if normalized_ext:
                return sticker_bytes, normalized_ext
            ext_by_mime = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/gif": ".gif",
            }
            return sticker_bytes, ext_by_mime.get(normalized_mime, ".png")

        # 优先尝试 PIL（webp 静态/部分动图）
        png_bytes = self._convert_image_bytes_to_png(sticker_bytes)
        if png_bytes:
            return png_bytes, ".png"

        # 动态/视频贴纸再尝试 ffmpeg 抽首帧（例如 .webm）
        if is_animated or is_video:
            ffmpeg_png = await asyncio.to_thread(
                self._extract_first_frame_with_ffmpeg,
                sticker_bytes,
                normalized_ext or (".webm" if is_video else ".tgs"),
            )
            if ffmpeg_png:
                return ffmpeg_png, ".png"

        logger.warning(f"贴纸转换为 PNG 失败，降级为文件段: mime={normalized_mime}, ext={normalized_ext}")
        return None

    def _convert_image_bytes_to_png(self, image_bytes: bytes) -> Optional[bytes]:
        """使用 Pillow 将图片字节转为 PNG。"""
        try:
            from PIL import Image
            with Image.open(BytesIO(image_bytes)) as image:
                output = BytesIO()
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA")
                image.save(output, format="PNG")
                return output.getvalue()
        except Exception:
            return None

    def _extract_first_frame_with_ffmpeg(self, sticker_bytes: bytes, suffix: str) -> Optional[bytes]:
        """使用 ffmpeg 抽取贴纸首帧为 PNG。"""
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            return None

        try:
            with tempfile.TemporaryDirectory(prefix="tg_sticker_") as tmp_dir:
                input_path = Path(tmp_dir) / f"input{suffix or '.bin'}"
                output_path = Path(tmp_dir) / "frame.png"
                input_path.write_bytes(sticker_bytes)
                cmd = [
                    ffmpeg_bin,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(input_path),
                    "-frames:v",
                    "1",
                    str(output_path),
                ]
                subprocess.run(cmd, check=True, timeout=8)
                if output_path.exists():
                    return output_path.read_bytes()
        except Exception:
            return None

        return None

    def _extract_text_content(self, segments: List[ChatMessageSegment]) -> str:
        """提取文本内容"""
        text_parts = []
        for segment in segments:
            seg_type = getattr(segment, "type", None)
            # 兼容：ChatMessageSegment.Config.use_enum_values=True 时，type 可能已被序列化为字符串
            if isinstance(seg_type, str):
                seg_type_val = seg_type
            else:
                seg_type_val = getattr(seg_type, "value", str(seg_type or ""))
            if seg_type_val == ChatMessageSegmentType.TEXT.value:
                if getattr(segment, "text", None):
                    text_parts.append(segment.text)
        return "".join(text_parts)

    def _get_effective_sender_profile(
        self,
        message: Message,
        display_name: str = "",
        nickname: str = "",
    ) -> tuple[str, str, str]:
        effective_user_id = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        effective_sender_name = display_name or effective_user_id
        effective_sender_nickname = nickname or effective_sender_name
        return effective_user_id, effective_sender_name, effective_sender_nickname

    def _preview_canonical_attachment_identity(self, message: Message) -> tuple[str, str]:
        raw_user_id = str(getattr(getattr(message, "from_user", None), "id", "") or "").strip()
        raw_channel_id = self.adapter._get_channel_id(message.chat)
        channel_type = ChatType.PRIVATE if getattr(message.chat, "type", "") == "private" else ChatType.GROUP
        preview = preview_canonical_inbound_identity(
            adapter=self.adapter,
            raw_platform_userid=raw_user_id,
            raw_channel_id=raw_channel_id,
            channel_type=channel_type,
        )
        return preview.canonical_chat_key, preview.canonical_userid

    def _build_reference_ext(self, segments: List[ChatMessageSegment], default_chat_key: str) -> PlatformMessageExt:
        ref_segment = extract_primary_reference_segment(segments)
        if not ref_segment:
            return PlatformMessageExt()
        return PlatformMessageExt(
            ref_chat_key=ref_segment.ref_chat_key or default_chat_key,
            ref_msg_id=ref_segment.ref_msg_id,
            ref_sender_id=ref_segment.ref_sender_id,
        )

    async def _build_reference_segment_from_message(self, message: Message) -> Optional[ChatMessageSegment]:
        if not message or not getattr(message, "message_id", None):
            return None
        ref_sender_name = ""
        ref_sender_nickname = ""
        if getattr(message, "from_user", None):
            ref_sender_name, ref_sender_nickname = await self._get_user_display_info(message.from_user, message.chat)
        ref_sender_id, effective_ref_name, _ = self._get_effective_sender_profile(
            message,
            ref_sender_name,
            ref_sender_nickname,
        )
        ref_segments = await self._process_message_content(message, include_reference=False)
        return build_reference_segment(
            ref_msg_id=str(message.message_id),
            ref_chat_key=self.adapter.build_chat_key(message.chat),
            ref_sender_id=ref_sender_id,
            ref_sender_name=effective_ref_name,
            ref_send_timestamp=int(getattr(message, "date", None).timestamp()) if getattr(message, "date", None) else 0,
            ref_segments=ref_segments,
            max_text_len=int(getattr(config, "REFERENCE_TEXT_MAX_LEN", 120) or 120),
        )

    def _is_mentioned(self, message: Message, context: ContextTypes.DEFAULT_TYPE = None) -> bool:
        """检查是否被提及"""
        # 如果是私聊，默认为 @ 机器人
        if message.chat.type == "private":
            return True
            
        # 在群聊中检查是否被提及
        if not message.entities:
            return False
            
        # 获取机器人的用户名
        bot_username = None
        if context and context.bot:
            bot_username = context.bot.username
            
        # 检查是否有 @机器人 的实体
        for entity in message.entities:
            if entity.type == "mention":
                # 提取 mention 的文本
                start = entity.offset
                end = entity.offset + entity.length
                mention_text = message.text[start:end] if message.text else ""
                
                # 检查是否提及了机器人
                if bot_username and mention_text == f"@{bot_username}":
                    return True
                    
        return False

    async def _get_user_display_info(
        self,
        user,
        chat,
    ) -> tuple[str, str]:
        """获取用户显示信息
        
        优先使用 message.from_user 中已有的信息，避免不必要的 API 调用
        
        Returns:
            tuple[str, str]: (显示名称, 昵称)
        """
        # 构建完整的用户昵称（优先级：first_name + last_name > first_name > username > user_id）
        full_nickname = self._build_full_name(user)
        
        # 构建显示名称（用于 user_name 字段）
        display_name = (
            user.first_name  # 优先使用 first_name
            or user.username  # 然后是 username
            or str(user.id)   # 最后使用 user_id
        )
        
        # 对于私聊，直接返回基于 message.from_user 的信息
        if chat.type == "private":
            return display_name, full_nickname
        
        # 对于群聊，也直接使用 message.from_user 的信息
        # Telegram 的 message.from_user 已经包含了最新的用户信息
        # 没有必要额外调用 getChatMember API
        
        logger.debug(f"获取用户信息: display_name={display_name}, nickname={full_nickname}")
        return display_name, full_nickname
    
    async def _get_channel_display_name(self, chat) -> str:
        """获取频道/群聊的显示名称"""
        # 对于群聊，优先使用 title
        if chat.type in ["group", "supergroup", "channel"]:
            return chat.title or f"群聊 {chat.id}"
        
        # 对于私聊，使用对方的名称
        elif chat.type == "private":
            return (
                chat.first_name
                or chat.username
                or f"私聊 {chat.id}"
            )
        
        # 其他情况
        return str(chat.id)
    
    def _build_full_name(self, user) -> str:
        """构建用户的完整名称"""
        if hasattr(user, 'first_name') and hasattr(user, 'last_name'):
            if user.first_name and user.last_name:
                return f"{user.first_name} {user.last_name}"
            elif user.first_name:
                return user.first_name
            elif user.username:
                return user.username
        elif hasattr(user, 'first_name') and user.first_name:
            return user.first_name
        elif hasattr(user, 'username') and user.username:
            return user.username
        
        return str(getattr(user, 'id', 'Unknown'))
    
    def _build_full_name_from_dict(self, user_dict: dict) -> str:
        """从字典构建用户的完整名称"""
        first_name = user_dict.get("first_name", "")
        last_name = user_dict.get("last_name", "")
        username = user_dict.get("username", "")
        
        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        elif username:
            return username
        
        return user_dict.get("id", "Unknown")
    
    async def _get_channel_display_name(self, chat) -> str:
        """获取频道/群聊的显示名称"""
        # 对于群聊，优先使用 title
        if chat.type in ["group", "supergroup", "channel"]:
            return chat.title or f"群聊 {chat.id}"
        
        # 对于私聊，使用对方的名称
        elif chat.type == "private":
            return (
                chat.first_name
                or chat.username
                or f"私聊 {chat.id}"
            )
        
        # 其他情况
        return str(chat.id)
