"""Tool 注册表

全局 tool 注册中心，负责：
1. 注册 tool（系统 / 迁移 / 特权）
2. 根据上下文窗口权限 + scope 配置返回可用 tool（ToolSpec）
3. 执行 tool 调用（含硬拦截）
4. 从 handler 的类型注解自动生成 JSON Schema

主干约束：
- scope 判定在暴露阶段与执行阶段共用同一套逻辑，禁止分叉。
- 纯 Tool Runtime 的配置与描述语义统一收口到 `tool_runtime/*`。
- Tool handler 只接收显式 runtime 参数 / `tool_host`，不再出现任何旧上下文型入参。
"""
from __future__ import annotations

import inspect
import json
import types
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, List, Literal, Optional, Type, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.schemas.ir import MessagePart, ToolCall, ToolResult, ToolSpec
from holo_cortex_zero.services.tools.config import get_tool_config
from holo_cortex_zero.services.tools.host import HCZToolHostBridge
from holo_cortex_zero.services.tools.runtime_types import ToolAccessSnapshot, ToolSourceKind
from tool_runtime.config import ToolEnabledScope, scope_allows
from tool_runtime.registry import ToolRuntimeRegistry
from tool_runtime.result import ToolOutcome
from tool_runtime.spec import ToolCapabilityClass, ToolDescriptor


class _EmptyToolConfig(BaseModel):
    pass


_RUNTIME_HIDDEN_PARAM_NAMES = {
    "chat_key",
    "context_id",
    "dialog_chat_key",
    "active_dialog_id",
    "channel_id",
    "primary_user_id",
    "tool_host",
    "host",
    "host_bridge",
    "tool_config",
}

_SCOPE_VALUES: tuple[ToolEnabledScope, ...] = ("disabled", "normal_only", "advanced_only", "all")


@dataclass(frozen=True)
class ToolRuntimeBinding:
    """tool 执行期运行时绑定。"""

    context_id: str = ""
    dialog_chat_key: str = ""
    primary_user_id: str = ""
    permission_level: str = ""
    adapter_key: str = ""
    channel_id: str = ""
    container_key: str = ""
    allow_chat_key_override: bool = False


class _ToolMessageAPIProxy:
    """给 tool runtime 用的消息代理。"""

    def __init__(self, base_message_api: Any, runtime_env: "ToolRuntimeEnv") -> None:
        self._base_message_api = base_message_api
        self._runtime_env = runtime_env

    def _resolve_chat_key(self, chat_key: Any) -> str:
        raw_chat_key = str(chat_key or "").strip()
        logical_context_id = str(self._runtime_env.context_id or "").strip()
        dialog_chat_key = str(self._runtime_env.dialog_chat_key or self._runtime_env.chat_key or "").strip()
        if raw_chat_key and raw_chat_key != logical_context_id:
            return raw_chat_key
        return dialog_chat_key or raw_chat_key

    async def send_text(self, chat_key: str, message: str, runtime_env: Any = None, **kwargs: Any) -> Any:
        return await self._base_message_api.send_text(
            self._resolve_chat_key(chat_key),
            message,
            runtime_env or self._runtime_env,
            **kwargs,
        )

    async def send_image(self, chat_key: str, image_path: str, runtime_env: Any = None, **kwargs: Any) -> Any:
        return await self._base_message_api.send_image(
            self._resolve_chat_key(chat_key),
            image_path,
            runtime_env or self._runtime_env,
            **kwargs,
        )

    async def send_file(self, chat_key: str, file_path: str, runtime_env: Any = None, **kwargs: Any) -> Any:
        return await self._base_message_api.send_file(
            self._resolve_chat_key(chat_key),
            file_path,
            runtime_env or self._runtime_env,
            **kwargs,
        )

    async def push_system(self, chat_key: str, message: str, runtime_env: Any = None, **kwargs: Any) -> Any:
        return await self._base_message_api.push_system(
            self._resolve_chat_key(chat_key),
            message,
            runtime_env or self._runtime_env,
            **kwargs,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_message_api, name)


class ToolRuntimeEnv:
    """tool 内部运行时包装。"""

    def __init__(self, runtime: ToolRuntimeBinding) -> None:
        self._runtime = runtime
        self._message_proxy: Any = None
        self._tool_host: Any = None

    @property
    def context_id(self) -> str:
        return str(self._runtime.context_id or self._runtime.dialog_chat_key or "").strip()

    @property
    def dialog_chat_key(self) -> str:
        return str(self._runtime.dialog_chat_key or self._runtime.context_id or "").strip()

    @property
    def active_dialog_id(self) -> str:
        return self.dialog_chat_key

    @property
    def primary_user_id(self) -> str:
        return str(self._runtime.primary_user_id or "").strip()

    @property
    def from_user_id(self) -> str:
        return self.primary_user_id

    @property
    def permission_level(self) -> str:
        return str(self._runtime.permission_level or "normal").strip() or "normal"

    @property
    def chat_key(self) -> str:
        return self.dialog_chat_key

    @property
    def from_chat_key(self) -> str:
        return self.dialog_chat_key

    @property
    def adapter_key(self) -> str:
        return str(self._runtime.adapter_key or _split_chat_key(self.dialog_chat_key)[0] or "").strip()

    @property
    def channel_id(self) -> str:
        return str(self._runtime.channel_id or _split_chat_key(self.dialog_chat_key)[1] or "").strip()

    @property
    def container_key(self) -> str | None:
        value = str(self._runtime.container_key or "").strip()
        return value or None

    @property
    def db_chat_channel(self) -> Any:
        return None

    @property
    def ms(self) -> Any:
        if self._message_proxy is None:
            from holo_cortex_zero.api import message as base_message_api
            self._message_proxy = _ToolMessageAPIProxy(base_message_api, self)
        return self._message_proxy

    @property
    def tool_host(self) -> HCZToolHostBridge:
        if self._tool_host is None:
            self._tool_host = HCZToolHostBridge(runtime=self)
        return self._tool_host

    async def send_text(self, content: str, *, record: bool = True) -> Any:
        return await self.ms.send_text(self.dialog_chat_key, content, self, record=record)

    async def send_image(self, file_path: str, *, record: bool = True) -> Any:
        return await self.ms.send_image(self.dialog_chat_key, file_path, self, record=record)

    async def send_file(self, file_path: str, *, record: bool = True) -> Any:
        return await self.ms.send_file(self.dialog_chat_key, file_path, self, record=record)

    async def push_system(self, message: str, trigger_agent: bool = False) -> Any:
        return await self.ms.push_system(self.dialog_chat_key, message, self, trigger_agent=trigger_agent)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


@dataclass
class RegisteredTool:
    """已注册的 Tool。"""

    name: str
    display_name: str
    category: str
    handler: Callable[..., Coroutine[Any, Any, Any]]
    description: str
    parameters: Dict[str, Any]
    permission_level: str = "normal"
    source_kind: ToolSourceKind = "migrated"
    capability_class: ToolCapabilityClass = "user_facing"
    default_scope: ToolEnabledScope = "all"
    skip_llm_tool: bool = False
    inject_context: bool = True
    history_strategy: str = "tool_result"
    history_text_arg: str = "text"
    supports_multimodal_return: bool = False
    config: Any = None
    config_key: str = ""
    hard_limit_notice: str = ""

    def get_config(self) -> Any:
        """获取当前生效的 Tool 配置实例。

        优先读取 ConfigManager 中的最新实例，避免 registry 缓存把新配置写回旧对象。
        """
        if self.config_key:
            from holo_cortex_zero.core.core_utils import ConfigManager

            current = ConfigManager.get_config(self.config_key)
            if current is not None:
                if current is not self.config:
                    self.config = current
                return current
        return self.config

    def resolve_scope_mode(self) -> ToolEnabledScope:
        config_obj = self.get_config()
        raw = str(getattr(config_obj, "SCOPE_MODE", self.default_scope) or self.default_scope).strip()
        if raw not in _SCOPE_VALUES:
            return self.default_scope
        return raw  # type: ignore[return-value]

    def access_snapshot(self) -> ToolAccessSnapshot:
        scope_mode = self.resolve_scope_mode()
        return ToolAccessSnapshot(
            scope_mode=scope_mode,
            effective_normal_enabled=scope_allows(scope=scope_mode, permission_level="normal"),
            effective_advanced_enabled=scope_allows(scope=scope_mode, permission_level="advanced"),
        )

    def allows_context(self, permission_level: str) -> bool:
        return scope_allows(scope=self.resolve_scope_mode(), permission_level=permission_level)

    def to_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            permission_level=("advanced" if self.capability_class == "privileged" else "normal"),  # type: ignore[arg-type]
        )


class ToolRegistry:
    """全局 Tool 注册表。"""

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}
        self._runtime_registry = ToolRuntimeRegistry()

    def register(
        self,
        name: str,
        handler: Callable[..., Coroutine[Any, Any, Any]],
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
        permission_level: str = "normal",
        skip_llm_tool: bool = False,
        inject_context: bool = True,
        history_strategy: str = "tool_result",
        history_text_arg: str = "text",
        *,
        display_name: Optional[str] = None,
        category: str = "tool",
        source_kind: Optional[ToolSourceKind] = None,
        capability_class: Optional[ToolCapabilityClass] = None,
        default_scope: Optional[ToolEnabledScope] = None,
        supports_multimodal_return: bool = False,
        config_model: Optional[Type[BaseModel]] = None,
        hard_limit_notice: str = "",
    ) -> None:
        """注册一个 Tool。"""
        sanitized_parameters = extract_params_schema(handler) if parameters is None else _sanitize_parameters_schema(parameters)
        resolved_capability = capability_class or ("privileged" if permission_level == "advanced" else "user_facing")
        resolved_default_scope = default_scope or ("all" if resolved_capability == "user_facing" else "advanced_only")
        resolved_source_kind: ToolSourceKind = source_kind or (
            "privileged" if resolved_capability == "privileged" else "system"
        )
        resolved_config_model = config_model or _EmptyToolConfig
        descriptor = ToolDescriptor(
            tool_id=name,
            display_name=display_name or name,
            description=description,
            category=category,
            capability_class=resolved_capability,
            default_scope=resolved_default_scope,
            parameters_schema=sanitized_parameters,
            supports_multimodal_return=supports_multimodal_return,
            config_model=resolved_config_model,
            handler=handler,
        )
        self._runtime_registry.register(descriptor)
        config_obj = get_tool_config(descriptor)

        self._tools[name] = RegisteredTool(
            name=name,
            display_name=display_name or name,
            category=category,
            handler=handler,
            description=description,
            parameters=sanitized_parameters,
            permission_level=permission_level,
            source_kind=resolved_source_kind,
            capability_class=resolved_capability,
            default_scope=resolved_default_scope,
            skip_llm_tool=skip_llm_tool,
            inject_context=inject_context,
            history_strategy=history_strategy,
            history_text_arg=history_text_arg,
            supports_multimodal_return=supports_multimodal_return,
            config=config_obj,
            config_key=config_obj.__class__.get_config_key(),
            hard_limit_notice=hard_limit_notice,
        )
        logger.info(
            "注册 Tool: %s source_kind=%s capability=%s default_scope=%s inject_context=%s",
            name,
            resolved_source_kind,
            resolved_capability,
            resolved_default_scope,
            inject_context,
        )

    def get_tools_for_context(self, permission_level: str) -> List[ToolSpec]:
        specs: List[ToolSpec] = []
        for tool in self._tools.values():
            if tool.skip_llm_tool:
                continue
            if tool.allows_context(permission_level):
                specs.append(tool.to_spec())
        return specs

    def get_tool(self, name: str) -> Optional[RegisteredTool]:
        return self._tools.get(str(name or "").strip())

    def list_registered_tools(self) -> List[RegisteredTool]:
        return list(self._tools.values())

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    async def execute(
        self,
        call: ToolCall,
        permission_level: str,
        runtime: Optional[ToolRuntimeBinding] = None,
    ) -> ToolResult:
        """执行 Tool 调用。"""
        if not call.id:
            call.id = f"call_{uuid.uuid4().hex[:8]}"
            logger.debug("Tool call 缺少 id，自动生成: %s (name=%s)", call.id, call.name)

        tool = self._tools.get(call.name)
        if tool is None:
            logger.warning("未知 Tool 调用: %s args=%s", call.name, _tool_log_json(call.arguments))
            return ToolResult(
                call_id=call.id,
                parts=[MessagePart(type="text", text=f"Tool 不存在: {call.name}")],
                is_error=True,
                history_role="tool",
                trace_title=f"Tool 拒绝 | {call.name}",
                trace_summary="tool_not_found",
            )

        if not tool.allows_context(permission_level):
            logger.warning(
                "Tool 访问被硬拦截: tool=%s perm=%s scope=%s",
                call.name,
                permission_level,
                tool.resolve_scope_mode(),
            )
            return ToolResult(
                call_id=call.id,
                parts=[MessagePart(type="text", text=f"Tool 未启用或当前上下文无权限: {call.name}")],
                is_error=True,
                history_role="tool",
                trace_title=f"Tool 拒绝 | {call.name}",
                trace_summary="tool_disabled_or_forbidden",
            )

        runtime_binding = _normalize_runtime_binding(runtime=runtime, permission_level=permission_level)
        if not runtime_binding.context_id:
            logger.warning("Tool 运行时缺少 context_id: tool=%s args=%s", call.name, _tool_log_json(call.arguments))
            return ToolResult(
                call_id=call.id,
                parts=[MessagePart(type="text", text=f"Tool 运行时缺少 context_id: {call.name}")],
                is_error=True,
                history_role="tool",
                trace_title=f"Tool 拒绝 | {call.name}",
                trace_summary="tool_runtime_missing_context_id",
            )
        if not runtime_binding.dialog_chat_key:
            logger.warning("Tool 运行时缺少 dialog_chat_key: tool=%s args=%s", call.name, _tool_log_json(call.arguments))
            return ToolResult(
                call_id=call.id,
                parts=[MessagePart(type="text", text=f"Tool 运行时缺少 dialog_chat_key: {call.name}")],
                is_error=True,
                history_role="tool",
                trace_title=f"Tool 拒绝 | {call.name}",
                trace_summary="tool_runtime_missing_dialog_chat_key",
            )

        try:
            sig = inspect.signature(tool.handler)
            kwargs: Dict[str, Any] = {}
            runtime_env = _build_tool_runtime_env(runtime_binding)
            current_tool_config = tool.get_config()

            explicit_param_names: set[str] = set()
            accepts_unknown_kwargs = False
            for param_name, param in sig.parameters.items():
                if param.kind is inspect.Parameter.VAR_KEYWORD:
                    accepts_unknown_kwargs = True
                    continue
                explicit_param_names.add(param_name)
                if param_name == "tool_config":
                    kwargs[param_name] = current_tool_config
                elif param_name in _RUNTIME_HIDDEN_PARAM_NAMES:
                    kwargs[param_name] = _derive_runtime_arg_value(
                        param_name=param_name,
                        call=call,
                        runtime=runtime_binding,
                        runtime_env=runtime_env,
                    )
                elif param_name in call.arguments:
                    kwargs[param_name] = call.arguments[param_name]
                elif param.default is inspect.Parameter.empty:
                    kwargs[param_name] = call.arguments.get(param_name)

            if accepts_unknown_kwargs:
                for arg_name, arg_value in call.arguments.items():
                    if not isinstance(arg_name, str):
                        continue
                    if arg_name in explicit_param_names or arg_name in _RUNTIME_HIDDEN_PARAM_NAMES:
                        continue
                    kwargs[arg_name] = arg_value

            result = await tool.handler(**kwargs)
            normalized_result = _normalize_tool_result(call_id=call.id, result=result)
            logger.info(
                "tool=%s call_id=%s context=%s dialog=%s scope=%s args=%s result_preview=%s",
                call.name,
                call.id,
                runtime_binding.context_id or "<empty>",
                runtime_binding.dialog_chat_key or "<empty>",
                tool.resolve_scope_mode(),
                _tool_log_json(call.arguments),
                _tool_result_preview(normalized_result),
            )
            return normalized_result
        except Exception as e:
            logger.error(
                "Tool %s 执行错误: %s (call_id=%s, args=%s)",
                call.name,
                e,
                call.id,
                _tool_log_json(call.arguments),
                exc_info=True,
            )
            return ToolResult(
                call_id=call.id,
                parts=[MessagePart(type="text", text=f"工具执行错误: {e}")],
                is_error=True,
                history_role="tool",
                trace_title=f"Tool 异常 | {call.name}",
                trace_summary="tool_execution_error",
            )

    @property
    def tool_count(self) -> int:
        return len(self._tools)



def _sanitize_parameters_schema(parameters: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(parameters or {})
    raw_properties = sanitized.get("properties")
    if isinstance(raw_properties, dict):
        properties = dict(raw_properties)
        for hidden_name in _RUNTIME_HIDDEN_PARAM_NAMES:
            properties.pop(hidden_name, None)
        sanitized["properties"] = properties

    raw_required = sanitized.get("required")
    if isinstance(raw_required, list):
        sanitized["required"] = [
            item for item in raw_required
            if str(item or "").strip() not in _RUNTIME_HIDDEN_PARAM_NAMES
        ]
    return sanitized


def _split_chat_key(chat_key: str) -> tuple[str, str]:
    raw = str(chat_key or "").strip()
    if not raw or "-" not in raw:
        return "", ""
    adapter_key, channel_id = raw.split("-", 1)
    return adapter_key.strip(), channel_id.strip()


def _normalize_runtime_binding(*, runtime: Optional[ToolRuntimeBinding], permission_level: str) -> ToolRuntimeBinding:
    binding = runtime or ToolRuntimeBinding()
    context_id = str(binding.context_id or "").strip()
    dialog_chat_key = str(binding.dialog_chat_key or "").strip()
    adapter_key = str(binding.adapter_key or "").strip()
    channel_id = str(binding.channel_id or "").strip()
    inferred_adapter, inferred_channel = _split_chat_key(dialog_chat_key)
    return ToolRuntimeBinding(
        context_id=context_id,
        dialog_chat_key=dialog_chat_key,
        primary_user_id=str(binding.primary_user_id or "").strip(),
        permission_level=str(binding.permission_level or permission_level or "normal").strip() or "normal",
        adapter_key=adapter_key or inferred_adapter,
        channel_id=channel_id or inferred_channel,
        container_key=str(binding.container_key or "").strip(),
        allow_chat_key_override=binding.allow_chat_key_override,
    )



def _build_tool_runtime_env(runtime: ToolRuntimeBinding) -> ToolRuntimeEnv:
    return ToolRuntimeEnv(runtime)



def _derive_runtime_arg_value(
    *,
    param_name: str,
    call: ToolCall,
    runtime: ToolRuntimeBinding,
    runtime_env: Any,
) -> Any:
    if param_name in {"tool_host", "host", "host_bridge"}:
        return runtime_env.tool_host

    if param_name == "chat_key":
        explicit_chat_key = str(call.arguments.get(param_name) or "").strip()
        if runtime.allow_chat_key_override and explicit_chat_key:
            return explicit_chat_key
        return str(runtime.dialog_chat_key or "").strip()

    if param_name == "context_id":
        return str(runtime.context_id or runtime.dialog_chat_key or "").strip()

    if param_name in {"dialog_chat_key", "active_dialog_id"}:
        return str(runtime.dialog_chat_key or runtime.context_id or "").strip()

    if param_name == "primary_user_id":
        return str(runtime.primary_user_id or "").strip()

    if param_name == "channel_id":
        return str(runtime.channel_id or "").strip()

    raise KeyError(param_name)



def _tool_log_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return repr(value)



def _tool_result_preview(result: Any) -> str:
    if isinstance(result, ToolResult):
        preview_parts = []
        for part in result.parts[:3]:
            preview_parts.append({
                "type": part.type,
                "text": str(part.text or "")[:120],
                "url": str(part.url or "")[:120],
                "meta": dict(part.meta or {}),
            })
        return _tool_log_json({
            "is_error": result.is_error,
            "history_role": result.history_role,
            "parts": preview_parts,
        })
    return _tool_log_json(result)



def _normalize_tool_result(*, call_id: str, result: Any) -> ToolResult:
    if isinstance(result, ToolResult):
        result.call_id = call_id
        return result

    if isinstance(result, ToolOutcome):
        return ToolResult(
            call_id=call_id,
            parts=[
                MessagePart(
                    type=part.type,
                    text=part.text,
                    url=part.url,
                    data=part.data,
                    mime_type=part.mime_type,
                    detail=part.detail,
                    meta=dict(part.meta or {}),
                )
                for part in result.parts
            ],
            is_error=result.is_error,
            history_role=result.history_role,
            trace_title=result.trace_title,
            trace_summary=result.trace_summary,
        )

    if result is None:
        return ToolResult(call_id=call_id, parts=[])

    if isinstance(result, str):
        return ToolResult(call_id=call_id, parts=[MessagePart(type="text", text=result)])

    if isinstance(result, (dict, list)):
        return ToolResult(
            call_id=call_id,
            parts=[MessagePart(type="text", text=json.dumps(result, ensure_ascii=False, indent=2, default=str))],
        )

    return ToolResult(call_id=call_id, parts=[MessagePart(type="text", text=str(result))])



def extract_params_schema(handler: Callable) -> Dict[str, Any]:
    """从 handler 的类型注解 + docstring 自动生成 JSON Schema。"""
    try:
        annotations = get_type_hints(handler)
    except Exception:
        annotations = {}

    sig = inspect.signature(handler)
    from holo_cortex_zero.core.prompt_defaults import render_identity_prompt

    doc = render_identity_prompt(inspect.getdoc(handler) or "")

    properties: Dict[str, Any] = {}
    required: List[str] = []

    def _annotation_to_schema(annotation: Any) -> Dict[str, Any]:
        origin = get_origin(annotation)
        args = get_args(annotation)

        if annotation in {str, int, float, bool}:
            return {
                str: {"type": "string"},
                int: {"type": "integer"},
                float: {"type": "number"},
                bool: {"type": "boolean"},
            }[annotation]

        if annotation in {dict, Dict} or origin in {dict, Dict}:
            return {"type": "object"}

        if annotation in {list, List, tuple, set} or origin in {list, List, tuple, set}:
            item_schema = {"type": "string"}
            if args:
                resolved_item_schema = _annotation_to_schema(args[0])
                if resolved_item_schema.get("type"):
                    item_schema = resolved_item_schema
            return {"type": "array", "items": item_schema}

        if origin in {Union, types.UnionType}:
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return _annotation_to_schema(non_none_args[0])

        return {"type": "string"}

    for name, param in sig.parameters.items():
        if name in _RUNTIME_HIDDEN_PARAM_NAMES:
            continue

        py_type = annotations.get(name, str)
        param_desc = _extract_param_description(doc, name)

        prop: Dict[str, Any] = _annotation_to_schema(py_type)
        if param_desc:
            prop["description"] = param_desc

        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return _sanitize_parameters_schema(
        {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    )



def _extract_param_description(doc: str, param_name: str) -> str:
    if not doc:
        return ""

    import re

    patterns = [
        rf"{param_name}\s*\([^)]*\)\s*:\s*(.+?)(?:\n|$)",
        rf"{param_name}\s*:\s*(.+?)(?:\n|$)",
        rf"@param\s+{param_name}\s+(.+?)(?:\n|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, doc, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


# 全局单例
# 说明：Tool Core 只通过这一入口注册到宿主，不再允许 legacy bridge 并行成为另一条主干。
tool_registry = ToolRegistry()
