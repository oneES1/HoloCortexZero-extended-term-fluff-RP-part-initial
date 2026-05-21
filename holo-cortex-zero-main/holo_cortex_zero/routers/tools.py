from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.services.tools.registry import RegisteredTool, tool_registry
from holo_cortex_zero.services.platform_admin import PlatformAdminPrincipal, get_current_active_platform_admin
from holo_cortex_zero.services.platform_admin import require_platform_role
from holo_cortex_zero.services.user.role import Role

router = APIRouter(prefix="/tools", tags=["Tools"])


class UpdateToolScopeBody(BaseModel):
    scope_mode: str


_SCOPE_CHOICES = {"disabled", "normal_only", "advanced_only", "all"}


def _tool_list_item(tool: RegisteredTool) -> Dict[str, object]:
    snapshot = tool.access_snapshot()
    return {
        "tool_id": tool.name,
        "display_name": tool.display_name,
        "description": tool.description,
        "category": tool.category,
        "capability_class": tool.capability_class,
        "scope_mode": snapshot.scope_mode,
        "effective_normal_enabled": snapshot.effective_normal_enabled,
        "effective_advanced_enabled": snapshot.effective_advanced_enabled,
        "config_key": tool.config_key,
        "supports_multimodal_return": tool.supports_multimodal_return,
    }


@router.get("", summary="获取 Tool 列表")
@require_platform_role(Role.Admin)
async def get_tools(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    tools = sorted(tool_registry.list_registered_tools(), key=lambda item: item.name)
    return Ret.success(msg="获取成功", data=[_tool_list_item(tool) for tool in tools])


@router.get("/{tool_id}", summary="获取 Tool 详情")
@require_platform_role(Role.Admin)
async def get_tool_detail(tool_id: str, _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    tool = tool_registry.get_tool(tool_id)
    if tool is None:
        return Ret.fail(msg="Tool 不存在")

    payload = _tool_list_item(tool)
    payload.update(
        {
            "parameters_schema": tool.parameters,
            "hard_limit_notice": tool.hard_limit_notice,
            "trace_behavior": {
                "inject_context": tool.inject_context,
                "history_strategy": tool.history_strategy,
            },
            "history_role_default": "payload_based",
        }
    )
    return Ret.success(msg="获取成功", data=payload)


@router.post("/{tool_id}/scope", summary="更新 Tool 启用范围")
@require_platform_role(Role.Admin)
async def update_tool_scope(
    tool_id: str,
    body: UpdateToolScopeBody = Body(...),
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    tool = tool_registry.get_tool(tool_id)
    if tool is None:
        return Ret.fail(msg="Tool 不存在")

    scope_mode = str(body.scope_mode or "").strip()
    if scope_mode not in _SCOPE_CHOICES:
        return Ret.fail(msg="非法 scope_mode")

    config_obj = tool.get_config()
    config_obj.SCOPE_MODE = scope_mode
    config_obj.dump_config()
    return Ret.success(msg="更新成功")
