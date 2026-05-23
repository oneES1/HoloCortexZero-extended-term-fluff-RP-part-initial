from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Sequence


@dataclass(frozen=True)
class ToolContextIdentity:
    context_id: str
    dialog_chat_key: str
    user_id: str
    permission_level: str
    adapter_key: str = ""
    channel_id: str = ""


@dataclass
class ManagedFileRef:
    managed_path: str
    local_path: str = ""
    mime_type: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolUserLookupResult:
    unique_id: str
    adapter_key: str
    platform_userid: str
    username: str
    is_active: bool
    is_prevent_trigger: bool


class ToolHostBridge(Protocol):
    async def log(self, level: str, message: str, **fields: Any) -> None:
        ...

    def now(self) -> Any:
        ...

    async def http_request(self, **kwargs: Any) -> Any:
        ...

    async def read_local_bytes(self, path: str | Path) -> bytes:
        ...

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
        ...

    async def resolve_media_ref(self, ref: str) -> str:
        ...

    async def invoke_model(self, model_group: str, payload: Dict[str, Any]) -> Any:
        ...

    def get_context_identity(self) -> ToolContextIdentity:
        ...

    async def block_store_get(self, context_id: str) -> Optional[Dict[str, Any]]:
        ...

    async def block_store_set(self, context_id: str, payload: Dict[str, Any]) -> None:
        ...

    async def lookup_user(self, user_identifier: str) -> Optional[Dict[str, Any]]:
        ...

    async def apply_user_block(
        self,
        unique_id: str,
        *,
        block_type: str,
        expire_time: Optional[int],
    ) -> bool:
        ...

    async def clear_user_block(self, unique_id: str, *, block_type: str) -> bool:
        ...

    async def list_files(self, path: str, *, max_depth: int = 3, pattern: str = "*", project_root: str = "") -> str:
        ...

    async def read_text_file(
        self,
        path: str,
        *,
        start_line: int = 1,
        end_line: Optional[int] = None,
        project_root: str = "",
    ) -> str:
        ...

    async def search_text(
        self,
        query: str,
        *,
        path: str = ".",
        file_pattern: str = "",
        max_results: int = 20,
        project_root: str = "",
    ) -> str:
        ...

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
        ...

    async def write_text_file(self, path: str, content: str, *, project_root: str = "") -> str:
        ...

    async def apply_text_patch(self, path: str, old_text: str, new_text: str, *, project_root: str = "") -> str:
        ...

    async def send_text(self, content: str, **kwargs: Any) -> Any:
        ...

    async def send_file(self, file_path: str, *, ref_msg_id: str = "") -> str:
        ...

    async def read_state_json(self, tool_id: str, file_name: str, *, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...

    async def write_state_json(self, tool_id: str, file_name: str, payload: Dict[str, Any]) -> None:
        ...
