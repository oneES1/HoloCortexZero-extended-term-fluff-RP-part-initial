from __future__ import annotations

import asyncio
import mimetypes
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from holo_cortex_zero.adapters.interface.schemas.platform import (
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformSendSegment,
    PlatformSendSegmentType,
)
from holo_cortex_zero.adapters.utils import adapter_utils
from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.services.system_voice.embedding import cosine_similarity, embed_text

try:
    import magic  # type: ignore
except Exception:  # pragma: no cover
    magic = None


_TRAILING_DIGITS_RE = re.compile(r"\d+$")
_CONTROL_CHAR_RE = re.compile(r"[\u0000-\u0008\u000B\u000C\u000E-\u001F]")
_WHITESPACE_RE = re.compile(r"\s+")

_DEFAULT_EMOJI_HOST_DIR = Path(OsEnv.WORKSPACE_ROOT) / "emoji"


@dataclass(frozen=True)
class EmojiDispatchResult:
    sent_with_emoji: bool
    reason: str
    response: Optional[PlatformSendResponse] = None
    matched_tag: str = ""
    file_path: str = ""
    mime_type: str = ""


class SystemEmojiService:
    def __init__(self) -> None:
        self._init_lock = asyncio.Lock()
        self._dispatch_lock = asyncio.Lock()
        self._initialized = False
        self._host_dir = _DEFAULT_EMOJI_HOST_DIR
        self._dir_mtime_ns = -1
        self._file_count = 0
        self._indexed_file_count = 0
        self._tag_to_paths: Dict[str, List[Path]] = {}
        self._tag_embeddings: Dict[str, List[float]] = {}

    def _resolve_host_dir(self) -> Path:
        raw = str(getattr(config, "SYSTEM_EMOJI_HOST_DIR", "") or "").strip()
        return Path(raw or str(_DEFAULT_EMOJI_HOST_DIR))

    @staticmethod
    def _sanitize_text(text: str) -> str:
        cleaned = _CONTROL_CHAR_RE.sub("", str(text or "")).strip()
        return _WHITESPACE_RE.sub(" ", cleaned).strip()

    @staticmethod
    def _extract_tag(path: Path) -> str:
        stem = str(path.stem or "").strip().lower()
        if not stem:
            return ""
        tag = _TRAILING_DIGITS_RE.sub("", stem).strip("_- ")
        return tag or stem

    def _iter_files(self) -> List[Path]:
        if not self._host_dir.exists():
            return []
        return sorted([item for item in self._host_dir.iterdir() if item.is_file()], key=lambda item: item.name)

    def _count_files(self) -> int:
        if not self._host_dir.exists():
            return 0
        return sum(1 for item in self._host_dir.iterdir() if item.is_file())

    def _get_dir_mtime_ns(self) -> int:
        try:
            return self._host_dir.stat().st_mtime_ns
        except Exception:
            return -1

    def _detect_mime_type(self, file_path: Path) -> str:
        try:
            if magic is not None:
                mime_type = str(magic.from_file(str(file_path), mime=True) or "").strip()
                if mime_type:
                    return mime_type
        except Exception as e:
            logger.warning(f"system_emoji MIME 探测失败，回退扩展名猜测: path={file_path} err={e}")
        return mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    async def initialize_runtime(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            self._host_dir = self._resolve_host_dir()
            if self._host_dir.is_symlink():
                self._host_dir.resolve().mkdir(parents=True, exist_ok=True)
            elif self._host_dir.exists() and not self._host_dir.is_dir():
                raise NotADirectoryError(f"system_emoji host_dir 不是目录: {self._host_dir}")
            else:
                self._host_dir.mkdir(parents=True, exist_ok=True)
            try:
                self._refresh_index(reason="startup")
            except Exception as e:
                logger.error(f"system_emoji 刷新索引失败，已继续: {e}", exc_info=True)
            self._initialized = True
            logger.info(
                "system_emoji 运行时初始化完成: "
                f"host_dir={self._host_dir} file_count={self._file_count} tags={len(self._tag_to_paths)}"
            )

    def _refresh_index(self, *, reason: str) -> None:
        files = self._iter_files()
        tag_to_paths: Dict[str, List[Path]] = {}
        for file_path in files:
            tag = self._extract_tag(file_path)
            if not tag:
                logger.warning(f"system_emoji 跳过无法提取标签的文件: {file_path.name}")
                continue
            tag_to_paths.setdefault(tag, []).append(file_path)

        for paths in tag_to_paths.values():
            paths.sort(key=lambda item: item.name)

        current_tags = set(tag_to_paths)
        for removed_tag in list(self._tag_embeddings):
            if removed_tag not in current_tags:
                self._tag_embeddings.pop(removed_tag, None)

        self._tag_to_paths = tag_to_paths
        self._file_count = len(files)
        self._indexed_file_count = len(files)
        self._dir_mtime_ns = self._get_dir_mtime_ns()
        logger.info(
            "system_emoji 已刷新内存标签索引: "
            f"reason={reason} file_count={self._file_count} tags={len(self._tag_to_paths)}"
        )

    def _refresh_index_if_needed(self) -> None:
        current_mtime_ns = self._get_dir_mtime_ns()
        if current_mtime_ns == self._dir_mtime_ns:
            return

        current_count = self._count_files()
        if current_count == self._indexed_file_count:
            self._file_count = current_count
            self._dir_mtime_ns = current_mtime_ns
            logger.info(
                "system_emoji 检测到目录变动但文件数未变，按约定跳过重建: "
                f"file_count={current_count} indexed_file_count={self._indexed_file_count} host_dir={self._host_dir}"
            )
            return

        logger.info(
            "system_emoji 检测到文件数变化，开始重建内存索引: "
            f"indexed_file_count={self._indexed_file_count} new_count={current_count} host_dir={self._host_dir}"
        )
        self._refresh_index(reason="file_count_changed")

    async def maybe_dispatch_reply(self, *, chat_key: str, text: str) -> EmojiDispatchResult:
        try:
            await self.initialize_runtime()

            if not bool(getattr(config, "SYSTEM_EMOJI_ENABLED", True)):
                return EmojiDispatchResult(sent_with_emoji=False, reason="disabled")

            normalized_text = self._sanitize_text(text)
            if not normalized_text:
                return EmojiDispatchResult(sent_with_emoji=False, reason="empty_text")

            async with self._dispatch_lock:
                self._refresh_index_if_needed()

                if not self._tag_to_paths:
                    logger.info("system_emoji 当前宿主机目录无可用资源，跳过")
                    return EmojiDispatchResult(sent_with_emoji=False, reason="empty_library")

                trigger_probability = float(getattr(config, "SYSTEM_EMOJI_TRIGGER_PROBABILITY", 0.02) or 0.0)
                rng_value = random.random()
                if rng_value > trigger_probability:
                    return EmojiDispatchResult(sent_with_emoji=False, reason=f"probability_miss:{rng_value:.6f}")

                model_group = str(getattr(config, "SYSTEM_EMOJI_EMBEDDING_MODEL_GROUP", "") or "").strip()
                if not model_group:
                    return EmojiDispatchResult(sent_with_emoji=False, reason="missing_model_group")

                adapter = await adapter_utils.get_adapter_for_chat(chat_key)
                text_response = await adapter.forward_message(
                    PlatformSendRequest(
                        chat_key=chat_key,
                        segments=[PlatformSendSegment(type=PlatformSendSegmentType.TEXT, content=text)],
                    )
                )
                if not text_response.success:
                    logger.warning(f"system_emoji 文本前置发送失败，回退纯文本链路: {text_response.error_message}")
                    return EmojiDispatchResult(sent_with_emoji=False, reason="text_send_failed")

                query_embedding = await embed_text(normalized_text, model_group=model_group)
                best_tag = ""
                best_score = -1.0
                for tag, paths in sorted(self._tag_to_paths.items()):
                    if not paths:
                        continue
                    if tag not in self._tag_embeddings:
                        self._tag_embeddings[tag] = await embed_text(tag, model_group=model_group)
                    score = cosine_similarity(query_embedding, self._tag_embeddings.get(tag, []))
                    if score > best_score:
                        best_score = score
                        best_tag = tag

                if not best_tag:
                    logger.info(f"system_emoji 文本已发送，但未匹配到标签: chat={chat_key}")
                    return EmojiDispatchResult(
                        sent_with_emoji=True,
                        reason="text_only_no_matched_tag",
                        response=text_response,
                    )

                selected_path = random.choice(self._tag_to_paths[best_tag])
                mime_type = self._detect_mime_type(selected_path)
                segment_type = PlatformSendSegmentType.IMAGE if mime_type.startswith("image/") else PlatformSendSegmentType.FILE

                resource_response = await adapter.forward_message(
                    PlatformSendRequest(
                        chat_key=chat_key,
                        segments=[PlatformSendSegment(type=segment_type, file_path=str(selected_path))],
                    )
                )
                if not resource_response.success:
                    logger.warning(
                        "system_emoji 资源发送失败，已保留原始文本: "
                        f"chat={chat_key} tag={best_tag} path={selected_path} err={resource_response.error_message}"
                    )
                    return EmojiDispatchResult(
                        sent_with_emoji=True,
                        reason="text_only_after_resource_failed",
                        response=text_response,
                        matched_tag=best_tag,
                        file_path=str(selected_path),
                        mime_type=mime_type,
                    )

                logger.info(
                    "system_emoji 已先发原始文本，再补发资源: "
                    f"chat={chat_key} tag={best_tag} path={selected_path} mime={mime_type} score={best_score:.4f}"
                )
                return EmojiDispatchResult(
                    sent_with_emoji=True,
                    reason="text_then_resource_sent",
                    response=text_response,
                    matched_tag=best_tag,
                    file_path=str(selected_path),
                    mime_type=mime_type,
                )
        except Exception as e:
            logger.error(f"system_emoji 发送流程失败，已回退纯文本: chat={chat_key} err={e}", exc_info=True)
            return EmojiDispatchResult(sent_with_emoji=False, reason="pipeline_failed")


system_emoji_service = SystemEmojiService()
