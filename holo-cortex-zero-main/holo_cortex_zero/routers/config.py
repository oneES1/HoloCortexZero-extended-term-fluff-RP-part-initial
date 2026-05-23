from typing import Any, Dict, List, Literal, Optional, get_args

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.config import ModelConfigGroup, config, save_config
from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.services.config_service import UnifiedConfigService
from holo_cortex_zero.services.llm.connectivity import test_model_group_connectivity
from holo_cortex_zero.services.platform_admin import PlatformAdminPrincipal, get_current_active_platform_admin
from holo_cortex_zero.services.platform_admin import require_platform_role
from holo_cortex_zero.services.user.role import Role
from holo_cortex_zero.tools.common_util import get_app_version


class BatchUpdateConfig(BaseModel):
    """批量更新配置请求体"""

    configs: Dict[str, str]


router = APIRouter(prefix="/config", tags=["Config"])


def get_field_enum(field_type: Any) -> List[str] | None:
    """获取字段的枚举选项"""
    try:
        if hasattr(field_type, "__origin__") and field_type.__origin__ is Literal:
            return list(get_args(field_type))
    except Exception:
        pass
    return None


def get_field_extra(field: Any, key: str) -> Any:
    """获取字段的额外信息"""
    if hasattr(field, "json_schema_extra") and isinstance(field.json_schema_extra, dict):
        return field.json_schema_extra.get(key)
    return None


@router.get("/keys", summary="获取所有配置键列表")
@require_platform_role(Role.Admin)
async def get_config_keys(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取所有已注册的配置键列表"""
    try:
        config_keys = UnifiedConfigService.get_all_config_keys()
        return Ret.success(msg="获取成功", data=config_keys)
    except Exception as e:
        logger.error(f"获取配置键列表失败: {e}")
        return Ret.error(msg=f"获取失败: {e!s}")


@router.get("/info/{config_key}", summary="获取配置基本信息")
@require_platform_role(Role.Admin)
async def get_config_info(
    config_key: str,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取指定配置的基本信息"""
    try:
        config_info = UnifiedConfigService.get_config_info(config_key)
        if not config_info:
            return Ret.fail(msg=f"配置实例不存在: {config_key}")
        return Ret.success(msg="获取成功", data=config_info)
    except Exception as e:
        logger.error(f"获取配置信息失败: {config_key}, 错误: {e}")
        return Ret.error(msg=f"获取失败: {e!s}")


@router.get("/list/{config_key}", summary="获取指定配置的配置列表")
@require_platform_role(Role.Admin)
async def get_config_list(
    config_key: str,
    include_hidden: bool = Query(False, description="是否包含隐藏配置项"),
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取指定配置的配置列表"""
    try:
        config_list = UnifiedConfigService.get_config_list(config_key, include_hidden=include_hidden)
        return Ret.success(msg="获取成功", data=config_list)
    except Exception as e:
        logger.error(f"获取配置列表失败: {config_key}, 错误: {e}")
        return Ret.error(msg=f"获取失败: {e!s}")


@router.get("/get/{config_key}/{item_key}", summary="获取配置项值")
@require_platform_role(Role.Admin)
async def get_config_item(
    config_key: str,
    item_key: str,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取指定配置的配置项值"""
    try:
        config_item = UnifiedConfigService.get_config_item(config_key, item_key)
        if not config_item:
            return Ret.fail(msg="配置项不存在")
        return Ret.success(msg="获取成功", data=config_item)
    except Exception as e:
        logger.error(f"获取配置项失败: {config_key}.{item_key}, 错误: {e}")
        return Ret.error(msg=f"获取失败: {e!s}")


@router.post("/set/{config_key}/{item_key}", summary="设置配置项值")
@require_platform_role(Role.Admin)
async def set_config_value(
    config_key: str,
    item_key: str,
    value: str = Query(..., description="配置项值"),
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """设置指定配置的配置项值"""
    try:
        success, error_msg = UnifiedConfigService.set_config_value(config_key, item_key, value)
        if not success:
            return Ret.fail(msg=error_msg)
        return Ret.success(msg="设置成功")
    except Exception as e:
        logger.error(f"设置配置值失败: {config_key}.{item_key}, 错误: {e}")
        return Ret.error(msg=f"设置失败: {e!s}")


@router.post("/batch/{config_key}", summary="批量更新配置")
@require_platform_role(Role.Admin)
async def batch_update_config(
    config_key: str,
    body: BatchUpdateConfig,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """批量更新指定配置"""
    try:
        success, error_msg = UnifiedConfigService.batch_update_config(config_key, body.configs)
        if not success:
            return Ret.fail(msg=error_msg or "批量更新失败")

        # 立即保存配置到文件
        success, error_msg = UnifiedConfigService.save_config(config_key)
        if not success:
            return Ret.fail(msg=f"保存配置失败: {error_msg or '未知错误'}")

        return Ret.success(msg="批量更新成功")
    except Exception as e:
        logger.error(f"批量更新配置失败: {config_key}, 错误: {e}")
        return Ret.error(msg=f"更新失败: {e!s}")


@router.post("/save/{config_key}", summary="保存配置")
@require_platform_role(Role.Admin)
async def save_config_api(
    config_key: str,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """保存指定配置到文件"""
    try:
        success, error_msg = UnifiedConfigService.save_config(config_key)
        if not success:
            return Ret.fail(msg=f"保存失败: {error_msg or '未知错误'}")
        return Ret.success(msg="保存成功")
    except Exception as e:
        logger.error(f"保存配置失败: {config_key}, 错误: {e}")
        return Ret.error(msg=f"保存失败: {e!s}")


@router.post("/reload/{config_key}", summary="重置配置")
@require_platform_role(Role.Admin)
async def reload_config_api(
    config_key: str,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """重置指定配置"""
    try:
        success, error_msg = UnifiedConfigService.reload_config(config_key)
        if not success:
            return Ret.fail(msg=f"重置失败: {error_msg or '未知错误'}")
        return Ret.success(msg="重置成功")
    except Exception as e:
        logger.error(f"重置配置失败: {config_key}, 错误: {e}")
        return Ret.error(msg=f"重载失败: {e!s}")


# ==================== 模型组管理API ====================


@router.get("/model-groups", summary="获取模型组列表")
@require_platform_role(Role.Admin)
async def get_model_groups(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取所有模型组配置"""
    return Ret.success(msg="获取成功", data=config.MODEL_GROUPS)


@router.post("/model-groups/test", summary="测试模型组连通性")
@require_platform_role(Role.Admin)
async def test_model_group(
    model_config: ModelConfigGroup,
    group_name: Optional[str] = Query("", description="模型组名称，仅用于日志与反馈"),
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """对模型组做对应类型的最小连通性测试。"""
    result = await test_model_group_connectivity(model_config, group_name=group_name or "")
    return Ret.success(msg="测试完成", data=result)


@router.post("/model-groups/{group_name}", summary="更新模型组")
@require_platform_role(Role.Admin)
async def update_model_group(
    group_name: str,
    model_config: ModelConfigGroup,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """更新或添加模型组配置"""
    try:
        # 直接使用整个model_config对象
        config.MODEL_GROUPS[group_name] = model_config
        save_config()
        connectivity = await test_model_group_connectivity(model_config, group_name=group_name)
        return Ret.success(msg="更新成功", data={"connectivity": connectivity})
    except Exception as e:
        return Ret.fail(msg=f"更新失败: {e!s}")


@router.delete("/model-groups/{group_name}", summary="删除模型组")
@require_platform_role(Role.Admin)
async def delete_model_group(
    group_name: str,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """删除模型组配置"""
    try:
        if group_name not in config.MODEL_GROUPS:
            return Ret.fail(msg="模型组不存在")
        del config.MODEL_GROUPS[group_name]
        save_config()
        return Ret.success(msg="删除成功")
    except Exception as e:
        return Ret.fail(msg=f"删除失败: {e!s}")


@router.get("/model-types", summary="获取支持的模型类型列表")
@require_platform_role(Role.Admin)
async def get_model_types(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取支持的模型类型列表"""
    # 从 ModelConfigGroup 的 MODEL_TYPE 字段定义中获取所有类型
    model_types = get_args(ModelConfigGroup.model_fields["MODEL_TYPE"].annotation)

    # 构建类型与描述的映射
    type_info = {
        "chat": {
            "label": "聊天",
            "description": "用于对话的模型",
            "color": "primary",
            "icon": "Chat",
        },
        "embedding": {
            "label": "嵌入",
            "description": "用于将文本转换为向量的模型",
            "color": "secondary",
            "icon": "Code",
        },
        "draw": {
            "label": "绘图",
            "description": "用于生成图像的模型",
            "color": "warning",
            "icon": "Brush",
        },
    }

    # 返回类型和描述
    model_type_info = [
        {
            "value": t,
            "label": type_info.get(t, {}).get("label", t),
            "description": type_info.get(t, {}).get("description", ""),
            "color": type_info.get(t, {}).get("color", "default"),
            "icon": type_info.get(t, {}).get("icon", "EmojiObjects"),
        }
        for t in model_types
    ]

    return Ret.success(msg="获取成功", data=model_type_info)


@router.get("/version", summary="获取应用版本")
@require_platform_role(Role.User)
async def get_version(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取应用版本"""
    return Ret.success(msg="获取成功", data=get_app_version())
