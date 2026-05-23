from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.services.file_system.service import managed_file_service
from holo_cortex_zero.tools.common_util import (
    download_file,
    download_file_from_base64,
    download_file_from_bytes,
)


class QuarantineFileService:
    """普通用户图片隔离持久化服务。

    主干规则：
    - 仅用于普通用户图片的短期隔离落盘
    - 文件不进入高级文件系统（避免向模型暴露真实路径能力）
    - 默认 TTL = 48 小时，到期自动清理
    """

    TTL_SECONDS = 48 * 60 * 60

    def get_root(self) -> Path:
        root = Path(OsEnv.DATA_DIR) / "quarantine_uploads"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def is_quarantine_path(self, path: str | Path) -> bool:
        try:
            candidate = Path(path).resolve()
            return str(candidate).startswith(str(self.get_root().resolve()))
        except Exception:
            return False

    def sanitize_file_name(self, file_name: str) -> str:
        return managed_file_service.sanitize_file_name(file_name)

    def _build_name(self, original_name: str) -> str:
        safe_name = self.sanitize_file_name(original_name or "unknown_file")
        return f"q_{int(time.time())}_{uuid.uuid4().hex[:12]}_{safe_name}"

    def allocate_path(self, original_name: str) -> Path:
        root = self.get_root()
        for _ in range(32):
            candidate = root / self._build_name(original_name)
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"无法分配 quarantine 路径: {original_name}")

    def _expires_at(self) -> int:
        return int(time.time()) + self.TTL_SECONDS

    def cleanup_expired(self) -> int:
        root = self.get_root()
        now = int(time.time())
        deleted = 0
        for item in root.iterdir():
            try:
                if not item.is_file():
                    continue
                expires_at = int(item.stat().st_mtime) + self.TTL_SECONDS
                if expires_at > now:
                    continue
                item.unlink(missing_ok=True)
                deleted += 1
            except Exception as exc:
                logger.warning(f"quarantine 清理失败: path={item} err={exc}")
        if deleted:
            logger.info(f"quarantine 过期文件已清理: count={deleted}")
        return deleted

    def remove_if_expired(self, path: str | Path, *, expires_at: Optional[int]) -> bool:
        if not expires_at or int(expires_at) > int(time.time()):
            return False
        target = Path(path)
        if not self.is_quarantine_path(target):
            return False
        try:
            target.unlink(missing_ok=True)
            logger.info(f"quarantine 文件已按 TTL 删除: path={target} expires_at={expires_at}")
        except Exception as exc:
            logger.warning(f"quarantine 过期删除失败: path={target} err={exc}")
        return True

    async def ingest_from_url(self, url: str, *, from_chat_key: str, file_name: str = "", use_suffix: str = "") -> tuple[str, str, int]:
        self.cleanup_expired()
        temp_path, downloaded_name = await download_file(
            url,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        final_path = self.allocate_path(file_name or downloaded_name)
        shutil.move(temp_path, final_path)
        expires_at = self._expires_at()
        logger.info(f"quarantine 图片落盘(url): dst={final_path} expires_at={expires_at}")
        return str(final_path), final_path.name, expires_at

    async def ingest_from_bytes(self, data: bytes, *, from_chat_key: str, file_name: str = "", use_suffix: str = "") -> tuple[str, str, int]:
        self.cleanup_expired()
        temp_path, downloaded_name = await download_file_from_bytes(
            bytes_data=data,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        final_path = self.allocate_path(file_name or downloaded_name)
        shutil.move(temp_path, final_path)
        expires_at = self._expires_at()
        logger.info(f"quarantine 图片落盘(bytes): dst={final_path} expires_at={expires_at}")
        return str(final_path), final_path.name, expires_at

    async def ingest_from_base64(self, base64_str: str, *, from_chat_key: str, file_name: str = "", use_suffix: str = "") -> tuple[str, str, int]:
        self.cleanup_expired()
        temp_path, downloaded_name = await download_file_from_base64(
            base64_str=base64_str,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        final_path = self.allocate_path(file_name or downloaded_name)
        shutil.move(temp_path, final_path)
        expires_at = self._expires_at()
        logger.info(f"quarantine 图片落盘(base64): dst={final_path} expires_at={expires_at}")
        return str(final_path), final_path.name, expires_at

    def ingest_from_local_path(self, local_path: str, *, file_name: str = "", use_suffix: str = "") -> tuple[str, str, int]:
        self.cleanup_expired()
        source_path = Path(local_path)
        original_name = file_name or source_path.name or "unknown_file"
        if use_suffix and not original_name.endswith(use_suffix):
            original_name = f"{Path(original_name).stem}{use_suffix}"
        final_path = self.allocate_path(original_name)
        shutil.copy2(source_path, final_path)
        expires_at = self._expires_at()
        logger.info(f"quarantine 图片落盘(local): src={source_path} dst={final_path} expires_at={expires_at}")
        return str(final_path), final_path.name, expires_at


quarantine_file_service = QuarantineFileService()
