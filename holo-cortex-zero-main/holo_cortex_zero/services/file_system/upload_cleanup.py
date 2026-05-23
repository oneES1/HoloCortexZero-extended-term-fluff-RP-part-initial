from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import USER_UPLOAD_DIR


_DEFAULT_TTL_SECONDS = 6 * 60 * 60
_DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60
_DEFAULT_STARTUP_DELAY_SECONDS = 5
_FAILURE_SAMPLE_LIMIT = 5


@dataclass
class UploadCleanupStats:
    deleted_files: int = 0
    deleted_dirs: int = 0
    deleted_bytes: int = 0
    failed: int = 0
    failure_samples: list[str] = field(default_factory=list)

    def add_failure(self, path: Path, exc: Exception) -> None:
        self.failed += 1
        if len(self.failure_samples) < _FAILURE_SAMPLE_LIMIT:
            self.failure_samples.append(f"{path}: {type(exc).__name__}: {exc}")


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"uploads TTL 清理配置无效，使用默认值: {name}={raw!r} default={default}")
        return default
    if value < minimum:
        logger.warning(f"uploads TTL 清理配置低于下限，使用默认值: {name}={value} minimum={minimum} default={default}")
        return default
    return value


class UploadCleanupService:
    """uploads 临时缓存磁盘回收服务。

    主干规则：
    - 只处理 USER_UPLOAD_DIR，对应容器内默认 /app/data/uploads。
    - 只删除超过 TTL 的普通文件和清理后留下的空子目录。
    - 不改变附件入库主干；uploads 是临时缓存，过期媒体允许失效。
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None

    @property
    def enabled(self) -> bool:
        return _env_bool("HCZ_UPLOAD_CLEANUP_ENABLED", True)

    @property
    def ttl_seconds(self) -> int:
        return _env_int("HCZ_UPLOAD_CLEANUP_TTL_SECONDS", _DEFAULT_TTL_SECONDS, minimum=60)

    @property
    def interval_seconds(self) -> int:
        return _env_int("HCZ_UPLOAD_CLEANUP_INTERVAL_SECONDS", _DEFAULT_INTERVAL_SECONDS, minimum=60)

    @property
    def startup_delay_seconds(self) -> int:
        return _env_int("HCZ_UPLOAD_CLEANUP_STARTUP_DELAY_SECONDS", _DEFAULT_STARTUP_DELAY_SECONDS, minimum=0)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        if not self.enabled:
            logger.info("uploads TTL 清理已禁用: HCZ_UPLOAD_CLEANUP_ENABLED=false")
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._cleanup_loop(), name="uploads-ttl-cleanup")
        logger.info(
            f"uploads TTL 清理已启动: root={USER_UPLOAD_DIR} ttl_seconds={self.ttl_seconds} "
            f"interval_seconds={self.interval_seconds} startup_delay_seconds={self.startup_delay_seconds}"
        )

    async def stop(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        task = self._task
        if not task:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            self._stop_event = None
        logger.info("uploads TTL 清理已停止")

    async def _cleanup_loop(self) -> None:
        assert self._stop_event is not None
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self.startup_delay_seconds)
            return
        except asyncio.TimeoutError:
            pass

        while not self._stop_event.is_set():
            await asyncio.to_thread(self.cleanup_once)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue

    def cleanup_once(self) -> UploadCleanupStats:
        root = Path(USER_UPLOAD_DIR).resolve()
        ttl_seconds = self.ttl_seconds
        cutoff = time.time() - ttl_seconds
        start = time.perf_counter()
        stats = UploadCleanupStats()

        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
            logger.info(f"uploads TTL 清理跳过: root={root} reason=created_missing_root")
            return stats
        if not root.is_dir():
            logger.warning(f"uploads TTL 清理跳过: root={root} reason=not_directory")
            return stats

        for current_root, dirs, files in os.walk(root, topdown=False, followlinks=False):
            current_path = Path(current_root)
            for file_name in files:
                file_path = current_path / file_name
                self._delete_expired_file(file_path, cutoff, stats)

            if current_path == root:
                continue
            self._remove_empty_dir(current_path, stats)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            f"uploads TTL 清理完成: root={root} ttl_seconds={ttl_seconds} interval_seconds={self.interval_seconds} "
            f"deleted_files={stats.deleted_files} deleted_dirs={stats.deleted_dirs} "
            f"deleted_bytes={stats.deleted_bytes} failed={stats.failed} elapsed_ms={elapsed_ms}"
        )
        if stats.failure_samples:
            logger.warning(f"uploads TTL 清理部分失败: failed={stats.failed} samples={stats.failure_samples}")
        return stats

    def _delete_expired_file(self, file_path: Path, cutoff: float, stats: UploadCleanupStats) -> None:
        try:
            if file_path.is_symlink() or not file_path.is_file():
                return
            stat_result = file_path.stat()
            if stat_result.st_mtime > cutoff:
                return
            file_path.unlink()
            stats.deleted_files += 1
            stats.deleted_bytes += int(stat_result.st_size)
        except FileNotFoundError:
            return
        except Exception as exc:
            stats.add_failure(file_path, exc)

    def _remove_empty_dir(self, dir_path: Path, stats: UploadCleanupStats) -> None:
        try:
            dir_path.rmdir()
            stats.deleted_dirs += 1
        except FileNotFoundError:
            return
        except OSError:
            return
        except Exception as exc:
            stats.add_failure(dir_path, exc)


upload_cleanup_service = UploadCleanupService()
