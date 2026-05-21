from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.tools.common_util import (
    download_file,
    download_file_from_base64,
    download_file_from_bytes,
)


_DEFAULT_MANAGED_ROOT = Path(OsEnv.WORKSPACE_ROOT) / "shared"


class ManagedFileService:
    """高级文件系统服务。

    主干说明：
    - bot 侧永远只接触真实宿主机绝对路径
    - 默认高级附件仍托管到全局高级文件根
    - 共享主干允许在工作区内按需覆盖托管根（如 draw 成品）
    """

    def get_root(self, *, managed_root: str = "") -> Path:
        raw_override = str(managed_root or "").strip()
        if raw_override:
            candidate = Path(raw_override).expanduser()
            if not candidate.is_absolute():
                candidate = Path(OsEnv.WORKSPACE_ROOT) / candidate
            workspace_root = Path(OsEnv.WORKSPACE_ROOT).resolve()
            resolved = candidate.resolve()
            if resolved != workspace_root and workspace_root not in resolved.parents:
                raise ValueError(f"高级文件系统托管根必须位于工作区内: {resolved}")
            resolved.mkdir(parents=True, exist_ok=True)
            return resolved

        root = Path(str(getattr(config, "ADVANCED_FILE_SYSTEM_ROOT", str(_DEFAULT_MANAGED_ROOT)) or str(_DEFAULT_MANAGED_ROOT))).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def sanitize_subdir_name(self, subdir_name: str) -> str:
        raw = str(subdir_name or "").strip()
        if not raw:
            return ""
        parts = []
        for chunk in raw.replace("\\", "/").split("/"):
            safe = self.sanitize_file_name(chunk)
            if not safe or safe == ".":
                continue
            parts.append(safe)
        return "/".join(parts)

    def get_managed_dir(self, *, managed_subdir: str = "", managed_root: str = "") -> Path:
        root = self.get_root(managed_root=managed_root)
        safe_subdir = self.sanitize_subdir_name(managed_subdir)
        target = root / safe_subdir if safe_subdir else root
        target.mkdir(parents=True, exist_ok=True)
        return target

    def sanitize_file_name(self, file_name: str) -> str:
        raw = str(file_name or "").strip()
        if not raw:
            raw = "unknown_file"
        raw = raw.replace("/", "_").replace("\\", "_")
        raw = "".join(ch if ch >= " " and ch not in {":", "*", "?", '"', "<", ">", "|"} else "_" for ch in raw)
        raw = raw.strip(" ._") or "unknown_file"
        return raw

    def build_managed_name(self, original_name: str) -> str:
        now = datetime.now()
        safe_name = self.sanitize_file_name(original_name)
        prefix = f"{now.year % 100:02d}年{now.month}月{now.day}日{now.hour:02d}点{now.minute:02d}分{now.second:02d}秒"
        return f"{prefix}_{safe_name}"

    def allocate_path(self, original_name: str, *, managed_subdir: str = "", managed_root: str = "") -> Path:
        root = self.get_managed_dir(managed_subdir=managed_subdir, managed_root=managed_root)
        base_name = self.build_managed_name(original_name)
        candidate = root / base_name
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        for index in range(1, 1000):
            dup_candidate = root / f"{stem}_dup{index:02d}{suffix}"
            if not dup_candidate.exists():
                return dup_candidate
        raise RuntimeError(f"无法为文件分配托管路径: {original_name}")

    def is_managed_path(self, path: str | Path) -> bool:
        try:
            candidate = Path(path).resolve()
            return str(candidate).startswith(str(self.get_root().resolve()))
        except Exception:
            return False

    def resolve_outbound_local_path(
        self,
        raw_path: str,
        *,
        chat_key: str,
        container_key: Optional[str] = None,
    ) -> Tuple[Optional[str], str]:
        normalized = str(raw_path or "").strip()
        if not normalized:
            return None, "empty"

        path_obj = Path(normalized)
        if path_obj.is_absolute():
            if path_obj.exists():
                return str(path_obj.resolve()), "absolute"
            return None, "absolute_missing"

        return None, "invalid"

    async def ingest_from_url(self, url: str, *, from_chat_key: str, file_name: str = "", use_suffix: str = "", managed_subdir: str = "", managed_root: str = "") -> tuple[str, str]:
        temp_path, downloaded_name = await download_file(
            url,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        final_path = self.allocate_path(file_name or downloaded_name, managed_subdir=managed_subdir, managed_root=managed_root)
        shutil.move(temp_path, final_path)
        logger.info(f"高级文件系统托管完成(url): src={url} dst={final_path}")
        return str(final_path), final_path.name

    async def ingest_from_bytes(self, data: bytes, *, from_chat_key: str, file_name: str = "", use_suffix: str = "", managed_subdir: str = "", managed_root: str = "") -> tuple[str, str]:
        temp_path, downloaded_name = await download_file_from_bytes(
            bytes_data=data,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        final_path = self.allocate_path(file_name or downloaded_name, managed_subdir=managed_subdir, managed_root=managed_root)
        shutil.move(temp_path, final_path)
        logger.info(f"高级文件系统托管完成(bytes): dst={final_path} size={final_path.stat().st_size}")
        return str(final_path), final_path.name

    async def ingest_from_base64(self, base64_str: str, *, from_chat_key: str, file_name: str = "", use_suffix: str = "", managed_subdir: str = "", managed_root: str = "") -> tuple[str, str]:
        temp_path, downloaded_name = await download_file_from_base64(
            base64_str=base64_str,
            file_name=file_name,
            use_suffix=use_suffix,
            from_chat_key=from_chat_key,
        )
        final_path = self.allocate_path(file_name or downloaded_name, managed_subdir=managed_subdir, managed_root=managed_root)
        shutil.move(temp_path, final_path)
        logger.info(f"高级文件系统托管完成(base64): dst={final_path} size={final_path.stat().st_size}")
        return str(final_path), final_path.name

    def ingest_from_local_path(self, local_path: str, *, file_name: str = "", use_suffix: str = "", managed_subdir: str = "", managed_root: str = "") -> tuple[str, str]:
        source_path = Path(local_path)
        original_name = file_name or source_path.name or "unknown_file"
        if use_suffix and not original_name.endswith(use_suffix):
            original_name = f"{Path(original_name).stem}{use_suffix}"
        final_path = self.allocate_path(original_name, managed_subdir=managed_subdir, managed_root=managed_root)
        shutil.copy2(source_path, final_path)
        logger.info(f"高级文件系统托管完成(local): src={source_path} dst={final_path} size={final_path.stat().st_size}")
        return str(final_path), final_path.name

    def infer_name_from_url(self, url: str, fallback: str = "unknown_file") -> str:
        try:
            parsed = urlparse(url)
            name = Path(parsed.path).name
            return self.sanitize_file_name(name or fallback)
        except Exception:
            return self.sanitize_file_name(fallback)


managed_file_service = ManagedFileService()
