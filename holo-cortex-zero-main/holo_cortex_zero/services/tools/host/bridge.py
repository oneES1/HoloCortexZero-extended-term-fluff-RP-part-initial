from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from zoneinfo import ZoneInfo

import httpx

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.config import ModelConfigGroup
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.core.proxy_utils import normalize_proxy_url
from holo_cortex_zero.models.db_user import DBUser
from holo_cortex_zero.services.tools.host.image_generation import generate_image_via_chat
from holo_cortex_zero.services.file_system.service import managed_file_service
from tool_runtime.host import ManagedFileRef, ToolContextIdentity, ToolHostBridge, ToolUserLookupResult


_TOOL_STATE_DIR = Path(OsEnv.DATA_DIR) / "tool_state"
_TOOL_STATE_DIR.mkdir(parents=True, exist_ok=True)
_BLOCK_STORE_PATH = _TOOL_STATE_DIR / "block_store.json"
_DEFAULT_PROJECT_ROOT = str(Path(OsEnv.WORKSPACE_ROOT))
_DEFAULT_COMMAND_TIMEOUT = 60
_RG_EXCLUDES = ["!.git", "!__pycache__", "!node_modules"]
_SENSITIVE_FILE_NAMES = {".env", "credentials.json", "credentials.yaml"}
_SENSITIVE_FILE_EXTS = {".key", ".pem", ".p12", ".pfx"}


def _load_block_store() -> Dict[str, Any]:
    if not _BLOCK_STORE_PATH.exists():
        return {}
    try:
        payload = json.loads(_BLOCK_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_block_store(payload: Dict[str, Any]) -> None:
    _BLOCK_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _BLOCK_STORE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _split_user_identifier(user_identifier: str, fallback_adapter: str) -> tuple[str, str]:
    normalized = str(user_identifier or "").strip()
    if ":" in normalized:
        adapter_key, platform_userid = normalized.split(":", 1)
        return adapter_key.strip() or fallback_adapter, platform_userid.strip()
    return fallback_adapter, normalized


def _resolve_project_root(project_root: str) -> Path:
    raw_root = str(project_root or "").strip() or _DEFAULT_PROJECT_ROOT
    return Path(raw_root).expanduser().resolve()


def _is_within_root(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _resolve_project_path(raw_path: str, *, project_root: str) -> tuple[bool, str, Path | None, Path]:
    root = _resolve_project_root(project_root)
    raw = str(raw_path or ".").strip() or "."
    try:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
    except Exception as exc:
        return False, str(exc), None, root
    if not _is_within_root(resolved, root):
        return False, f"路径 {raw} 不在允许的目录 {root} 内", None, root
    return True, str(resolved), resolved, root


def _is_command_allowed(command: str, *, allowed_prefixes: Sequence[str], blocked_patterns: Sequence[str]) -> tuple[bool, str]:
    cmd = str(command or "").strip()
    if not cmd:
        return False, "命令不能为空"

    for pattern in blocked_patterns:
        if not pattern:
            continue
        if re.search(pattern, cmd):
            return False, f"命令匹配危险模式: {pattern}"

    for prefix in allowed_prefixes:
        normalized_prefix = str(prefix or "").strip()
        if normalized_prefix and cmd.startswith(normalized_prefix):
            return True, ""

    head = cmd.split()[0] if cmd.split() else cmd
    return False, f"命令 '{head}' 不在白名单中"


class HCZToolHostBridge(ToolHostBridge):
    def __init__(self, *, runtime: Any) -> None:
        self._runtime = runtime

    def _effective_chat_key(self, override: str = "") -> str:
        runtime = self._runtime
        return str(
            override
            or getattr(runtime, "dialog_chat_key", "")
            or getattr(runtime, "chat_key", "")
            or getattr(runtime, "context_id", "")
            or ""
        ).strip()

    def _effective_container_key(self) -> str | None:
        value = str(getattr(self._runtime, "container_key", "") or "").strip()
        return value or None

    def _effective_adapter_key(self) -> str:
        return str(getattr(self._runtime, "adapter_key", "") or "").strip()

    async def log(self, level: str, message: str, **fields: Any) -> None:
        payload = f"{message} | {fields}" if fields else message
        normalized = str(level or "info").lower()
        log_fn = getattr(logger, normalized, logger.info)
        log_fn(payload)

    def now(self) -> datetime:
        return datetime.now()

    async def http_request(self, **kwargs: Any) -> Any:
        timeout = kwargs.pop("timeout", 30.0)
        proxy = normalize_proxy_url(str(getattr(config, "DEFAULT_PROXY", "") or "").strip() or None)
        async with httpx.AsyncClient(timeout=timeout, proxy=proxy, trust_env=False) as client:
            response = await client.request(**kwargs)
            response.raise_for_status()
            return response

    async def read_local_bytes(self, path: str | Path) -> bytes:
        return Path(path).read_bytes()

    async def write_managed_file(
        self,
        bytes_or_path: bytes | str | Path,
        *,
        file_name: str,
        mime_type: str = "",
        chat_key: str = "",
        managed_subdir: str = "",
        managed_root: str = "",
    ) -> ManagedFileRef:
        effective_chat_key = self._effective_chat_key(chat_key)
        if isinstance(bytes_or_path, bytes):
            if not effective_chat_key:
                raise ValueError("tool host bridge 缺少 dialog_chat_key，无法写入托管文件")
            host_path, resolved_name = await managed_file_service.ingest_from_bytes(
                bytes_or_path,
                from_chat_key=effective_chat_key,
                file_name=file_name,
                managed_subdir=managed_subdir,
                managed_root=managed_root,
            )
        elif isinstance(bytes_or_path, (str, Path)):
            raw_path = str(bytes_or_path)
            if raw_path.startswith(("http://", "https://")):
                if not effective_chat_key:
                    raise ValueError("tool host bridge 缺少 dialog_chat_key，无法写入托管文件")
                host_path, resolved_name = await managed_file_service.ingest_from_url(
                    raw_path,
                    from_chat_key=effective_chat_key,
                    file_name=file_name,
                    managed_subdir=managed_subdir,
                    managed_root=managed_root,
                )
            elif raw_path.startswith("data:"):
                if not effective_chat_key:
                    raise ValueError("tool host bridge 缺少 dialog_chat_key，无法写入托管文件")
                host_path, resolved_name = await managed_file_service.ingest_from_base64(
                    raw_path,
                    from_chat_key=effective_chat_key,
                    file_name=file_name,
                    managed_subdir=managed_subdir,
                    managed_root=managed_root,
                )
            else:
                host_path, resolved_name = managed_file_service.ingest_from_local_path(
                    raw_path,
                    file_name=file_name,
                    managed_subdir=managed_subdir,
                    managed_root=managed_root,
                )
        else:
            raise TypeError(f"不支持的文件类型: {type(bytes_or_path)}")

        resolved_host_path = str(Path(host_path).resolve())
        resolved_mime = mime_type or mimetypes.guess_type(file_name or resolved_name)[0] or "application/octet-stream"
        return ManagedFileRef(managed_path=resolved_host_path, local_path=resolved_host_path, mime_type=resolved_mime)

    async def resolve_media_ref(self, ref: str) -> str:
        if not ref:
            return str(ref or "")
        raw_ref = str(ref or "").strip()
        if not raw_ref:
            return raw_ref
        path_obj = Path(raw_ref)
        if path_obj.is_absolute():
            return str(path_obj.resolve())
        effective_chat_key = self._effective_chat_key()
        if not effective_chat_key:
            return raw_ref
        resolved_path, path_kind = managed_file_service.resolve_outbound_local_path(
            raw_ref,
            chat_key=effective_chat_key,
            container_key=self._effective_container_key(),
        )
        if resolved_path:
            logger.info(
                "tool host resolved legacy media ref: raw=%s kind=%s resolved=%s",
                raw_ref,
                path_kind,
                resolved_path,
            )
            return resolved_path
        return raw_ref

    async def invoke_model(self, model_group: str, payload: Dict[str, Any]) -> Any:
        model = config.MODEL_GROUPS.get(model_group)
        if not isinstance(model, ModelConfigGroup):
            raise ValueError(f"模型组不存在: {model_group}")
        operation = str(payload.get("operation") or "").strip().lower()
        if operation == "image_generate":
            reference_images = payload.get("reference_images") or []
            normalized_refs: list[tuple[str, str]] = []
            if isinstance(reference_images, list):
                for item in reference_images:
                    if not isinstance(item, dict):
                        continue
                    image = str(item.get("image") or "").strip()
                    if not image:
                        continue
                    normalized_refs.append((image, str(item.get("description") or "").strip()))
            logger.info(
                "tool host image_generate: group=%s model=%s refs=%s stream=%s timeout=%s",
                model_group,
                model.CHAT_MODEL,
                len(normalized_refs),
                bool(payload.get("stream_mode")),
                int(payload.get("timeout") or 300),
            )
            return await generate_image_via_chat(
                model,
                str(payload.get("prompt") or "").strip(),
                timeout=float(payload.get("timeout") or 300.0),
                system_prompt=str(payload.get("system_prompt") or "").strip() or None,
                reference_images=normalized_refs or None,
                stream_mode=bool(payload.get("stream_mode")),
                image_detail=str(payload.get("image_detail") or "").strip() or None,
            )
        return {
            "model_group": model_group,
            "payload": payload,
            "model": model.CHAT_MODEL,
            "base_url": model.BASE_URL,
        }

    def get_context_identity(self) -> ToolContextIdentity:
        return ToolContextIdentity(
            context_id=str(getattr(self._runtime, "context_id", "") or getattr(self._runtime, "chat_key", "") or "").strip(),
            dialog_chat_key=str(getattr(self._runtime, "dialog_chat_key", "") or getattr(self._runtime, "chat_key", "") or "").strip(),
            user_id=str(getattr(self._runtime, "primary_user_id", "") or getattr(self._runtime, "from_user_id", "") or "").strip(),
            permission_level=str(getattr(self._runtime, "permission_level", "") or "normal").strip() or "normal",
            adapter_key=str(getattr(self._runtime, "adapter_key", "") or "").strip(),
            channel_id=str(getattr(self._runtime, "channel_id", "") or "").strip(),
        )

    async def block_store_get(self, context_id: str) -> Optional[Dict[str, Any]]:
        store = _load_block_store()
        payload = store.get(str(context_id or "").strip())
        return payload if isinstance(payload, dict) else None

    async def block_store_set(self, context_id: str, payload: Dict[str, Any]) -> None:
        store = _load_block_store()
        store[str(context_id or "").strip()] = payload
        _save_block_store(store)
        await self.log("info", "tool block store saved", context_id=context_id, keys=list(payload.keys()))

    async def lookup_user(self, user_identifier: str) -> Optional[ToolUserLookupResult]:
        adapter_key, platform_userid = _split_user_identifier(
            str(user_identifier or "").strip(),
            self._effective_adapter_key(),
        )
        if not adapter_key or not platform_userid:
            return None
        user = await DBUser.get_or_none(adapter_key=adapter_key, platform_userid=platform_userid)
        if user is None:
            return None
        from holo_cortex_zero.services.context_window.manager import context_window_manager

        sanitized_username = context_window_manager._sanitize_sender_name_for_context(
            user.platform_userid,
            user.username,
        )
        return ToolUserLookupResult(
            unique_id=user.unique_id,
            adapter_key=user.adapter_key,
            platform_userid=user.platform_userid,
            username=sanitized_username,
            is_active=user.is_active,
            is_prevent_trigger=user.is_prevent_trigger,
        )

    async def apply_user_block(self, unique_id: str, *, block_type: str, expire_time: Optional[int]) -> bool:
        adapter_key, platform_userid = _split_user_identifier(str(unique_id or "").strip(), fallback_adapter="")
        user = await DBUser.get_or_none(adapter_key=adapter_key, platform_userid=platform_userid)
        if user is None:
            return False

        resolved_expire = int(expire_time) if expire_time is not None else int(datetime(2999, 1, 1, tzinfo=ZoneInfo("UTC")).timestamp())
        expire_datetime = datetime.fromtimestamp(resolved_expire, tz=ZoneInfo("UTC"))

        if str(block_type or "").strip() == "prevent_trigger":
            user.prevent_trigger_until = expire_datetime
        else:
            user.ban_until = expire_datetime
        await user.save()
        return True

    async def clear_user_block(self, unique_id: str, *, block_type: str) -> bool:
        adapter_key, platform_userid = _split_user_identifier(str(unique_id or "").strip(), fallback_adapter="")
        user = await DBUser.get_or_none(adapter_key=adapter_key, platform_userid=platform_userid)
        if user is None:
            return False

        if str(block_type or "").strip() == "prevent_trigger":
            user.prevent_trigger_until = None
        else:
            user.ban_until = None
        await user.save()
        return True

    async def list_files(self, path: str, *, max_depth: int = 3, pattern: str = "*", project_root: str = "") -> str:
        safe, resolved_msg, resolved_path, _ = _resolve_project_path(path, project_root=project_root)
        if not safe or resolved_path is None:
            return f"错误: {resolved_msg}"

        try:
            proc = await asyncio.create_subprocess_exec(
                "find",
                str(resolved_path),
                "-maxdepth",
                str(max(0, int(max_depth))),
                "-name",
                str(pattern or "*") or "*",
                "-not",
                "-path",
                "*/.git/*",
                "-not",
                "-path",
                "*/__pycache__/*",
                "-not",
                "-path",
                "*/node_modules/*",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode not in {0, 1}:
                err = (stderr or b"").decode("utf-8", errors="replace").strip()
                return f"错误: {err or 'find 执行失败'}"
            output = (stdout or b"").decode("utf-8", errors="replace").strip()
            if not output:
                return "(空目录)"
            lines = output.splitlines()
            if len(lines) > 200:
                return "\n".join(lines[:200]) + f"\n... (共 {len(lines)} 项，已截断)"
            return output
        except Exception as exc:
            return f"错误: {exc}"

    async def read_text_file(
        self,
        path: str,
        *,
        start_line: int = 1,
        end_line: Optional[int] = None,
        project_root: str = "",
    ) -> str:
        safe, resolved_msg, resolved_path, _ = _resolve_project_path(path, project_root=project_root)
        if not safe or resolved_path is None:
            return f"错误: {resolved_msg}"

        try:
            with resolved_path.open("r", encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
            total = len(lines)
            start = max(0, int(start_line or 1) - 1)
            end = max(start, int(end_line)) if end_line is not None else total
            selected = lines[start:end]
            if len(selected) > 500:
                selected = selected[:500]
                return "".join(f"{start + index + 1:5d} | {line}" for index, line in enumerate(selected)) + f"\n... (文件共 {total} 行，已截断前 500 行)"
            return "".join(f"{start + index + 1:5d} | {line}" for index, line in enumerate(selected))
        except FileNotFoundError:
            return f"文件不存在: {resolved_path}"
        except Exception as exc:
            return f"读取错误: {exc}"

    async def search_text(
        self,
        query: str,
        *,
        path: str = ".",
        file_pattern: str = "",
        max_results: int = 20,
        project_root: str = "",
    ) -> str:
        safe, resolved_msg, resolved_path, _ = _resolve_project_path(path, project_root=project_root)
        if not safe or resolved_path is None:
            return f"错误: {resolved_msg}"

        max_hits = max(1, int(max_results or 1))
        try:
            if shutil.which("rg"):
                cmd = [
                    "rg",
                    "-n",
                    "--no-heading",
                    "--glob",
                    _RG_EXCLUDES[0],
                    "--glob",
                    _RG_EXCLUDES[1],
                    "--glob",
                    _RG_EXCLUDES[2],
                ]
                if file_pattern:
                    cmd.extend(["--glob", str(file_pattern)])
                cmd.extend([str(query), str(resolved_path)])
            else:
                include_pattern = str(file_pattern or "*") or "*"
                cmd = ["grep", "-rn", "--include", include_pattern, str(query), str(resolved_path)]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            stderr_text = (stderr or b"").decode("utf-8", errors="replace").strip()
            if proc.returncode not in {0, 1}:
                return f"搜索错误: {stderr_text or '搜索命令执行失败'}"
            output = (stdout or b"").decode("utf-8", errors="replace").strip()
            if not output:
                return "未找到匹配"
            lines = output.splitlines()
            if len(lines) > max_hits:
                return "\n".join(lines[:max_hits]) + f"\n... (共 {len(lines)} 条匹配)"
            return output
        except Exception as exc:
            return f"搜索错误: {exc}"

    async def run_command(
        self,
        command: str,
        *,
        cwd: str = "",
        timeout: int = 60,
        project_root: str = "",
        allowed_prefixes: Sequence[str] = (),
        blocked_patterns: Sequence[str] = (),
    ) -> str:
        allowed, reason = _is_command_allowed(
            command,
            allowed_prefixes=allowed_prefixes,
            blocked_patterns=blocked_patterns,
        )
        if not allowed:
            return f"命令被拒绝: {reason}"

        safe, resolved_msg, resolved_path, root = _resolve_project_path(cwd or ".", project_root=project_root)
        if not safe or resolved_path is None:
            return f"工作目录错误: {resolved_msg}"

        effective_timeout = min(max(1, int(timeout or _DEFAULT_COMMAND_TIMEOUT)), _DEFAULT_COMMAND_TIMEOUT)
        try:
            proc = await asyncio.create_subprocess_shell(
                str(command),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(resolved_path),
                env={**os.environ, "PWD": str(resolved_path), "PROJECT_ROOT": str(root)},
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=effective_timeout)
            output = (stdout or b"").decode("utf-8", errors="replace")
            if len(output) > 10000:
                output = output[:10000] + "\n... (输出已截断)"
            return f"[exit code: {proc.returncode}]\n{output}"
        except asyncio.TimeoutError:
            return f"命令执行超时（{effective_timeout}秒）"
        except Exception as exc:
            return f"执行错误: {exc}"

    async def write_text_file(self, path: str, content: str, *, project_root: str = "") -> str:
        safe, resolved_msg, resolved_path, _ = _resolve_project_path(path, project_root=project_root)
        if not safe or resolved_path is None:
            return f"错误: {resolved_msg}"

        file_name = resolved_path.name.lower()
        if file_name in _SENSITIVE_FILE_NAMES or resolved_path.suffix.lower() in _SENSITIVE_FILE_EXTS:
            return f"安全限制: 不允许写入敏感文件 {file_name}"

        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_path.write_text(str(content or ""), encoding="utf-8")
            return f"已写入 {resolved_path} ({len(str(content or ''))} 字符)"
        except Exception as exc:
            return f"写入错误: {exc}"

    async def apply_text_patch(self, path: str, old_text: str, new_text: str, *, project_root: str = "") -> str:
        safe, resolved_msg, resolved_path, _ = _resolve_project_path(path, project_root=project_root)
        if not safe or resolved_path is None:
            return f"错误: {resolved_msg}"

        try:
            content = resolved_path.read_text(encoding="utf-8")
            if old_text not in content:
                return "未找到要替换的文本片段"
            count = content.count(old_text)
            resolved_path.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
            return f"已替换 {resolved_path} 中的 1 处匹配（共 {count} 处）"
        except FileNotFoundError:
            return f"文件不存在: {resolved_path}"
        except Exception as exc:
            return f"修补错误: {exc}"

    async def send_text(self, content: str, **kwargs: Any) -> Any:
        if self._runtime is not None and hasattr(self._runtime, "send_text"):
            return await self._runtime.send_text(content, record=bool(kwargs.get("record", True)))
        return None

    async def send_file(self, file_path: str, *, ref_msg_id: str = "") -> str:
        raw = str(file_path or "").strip()
        if not raw:
            return "错误: file_path 不能为空"
        effective_runtime = self._runtime
        effective_chat_key = self._effective_chat_key()
        effective_ms = getattr(effective_runtime, "ms", None) if effective_runtime is not None else None
        if effective_runtime is None or effective_ms is None or not effective_chat_key:
            return "错误: send_file 缺少 runtime chat context"

        path_obj = Path(raw).expanduser()
        if not path_obj.is_absolute():
            return "错误: 只允许真实本地绝对路径"
        if not path_obj.exists() or not path_obj.is_file():
            return f"错误: 文件不存在或不可读: {path_obj}"

        mime_type = mimetypes.guess_type(str(path_obj))[0] or ""
        if mime_type.startswith("image/"):
            await effective_ms.send_image(effective_chat_key, str(path_obj), effective_runtime, ref_msg_id=ref_msg_id or None)
            logger.info(f"系统内置 send_file 已发送图片: chat_key={effective_chat_key} path={path_obj}")
            return f"已发送 {path_obj}"

        await effective_ms.send_file(effective_chat_key, str(path_obj), effective_runtime, ref_msg_id=ref_msg_id or None)
        logger.info(f"系统内置 send_file 已发送文件: chat_key={effective_chat_key} path={path_obj}")
        return f"已发送 {path_obj}"

    async def read_state_json(self, tool_id: str, file_name: str, *, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tool_dir = _TOOL_STATE_DIR / str(tool_id or "unknown")
        path = tool_dir / f"{str(file_name or 'state').strip() or 'state'}.json"
        if not path.exists():
            return dict(default or {})
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(default or {})
        return payload if isinstance(payload, dict) else dict(default or {})

    async def write_state_json(self, tool_id: str, file_name: str, payload: Dict[str, Any]) -> None:
        tool_dir = _TOOL_STATE_DIR / str(tool_id or "unknown")
        tool_dir.mkdir(parents=True, exist_ok=True)
        path = tool_dir / f"{str(file_name or 'state').strip() or 'state'}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
