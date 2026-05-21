from datetime import datetime, timezone
from typing import Optional, cast

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from tortoise.expressions import Q

from holo_cortex_zero import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.models.db_user import DBUser
from holo_cortex_zero.schemas.errors import PermissionDeniedError, UnauthorizedError
from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.schemas.user import UserUpdate
from holo_cortex_zero.services.platform_admin import PlatformAdminPrincipal, get_current_active_platform_admin
from holo_cortex_zero.services.user.role import Role, get_perm_role

router = APIRouter(prefix="/user-manager", tags=["UserManager"])


@router.get("/list", summary="获取用户列表")
async def list_users(
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取用户列表"""
    if _platform_admin.perm_level < Role.Admin:
        raise PermissionDeniedError

    # 构建查询
    query = DBUser.all()

    # 搜索
    if search:
        query = query.filter(
            Q(username__icontains=search) | Q(platform_userid__icontains=search),
        )

    # 排序
    if sort_by:
        order_by = sort_by
        if sort_order == "desc":
            order_by = f"-{sort_by}"
        query = query.order_by(order_by)
    else:
        query = query.order_by("-id")

    # 分页
    total = await query.count()
    users = await query.offset((page - 1) * page_size).limit(page_size)

    # 转换为响应格式
    user_list = []
    for user in users:
        user_list.append(
            {
                "id": user.id,
                "username": user.username,
                "adapter_key": user.adapter_key,
                "platform_userid": user.platform_userid,
                "unique_id": user.unique_id,
                "perm_level": user.perm_level,
                "perm_role": get_perm_role(user.perm_level),
                "login_time": user.login_time,
                "ban_until": user.ban_until,
                "prevent_trigger_until": user.prevent_trigger_until,
                "is_active": user.is_active,
                "is_prevent_trigger": user.is_prevent_trigger,
                "create_time": user.create_time,
                "update_time": user.update_time,
            },
        )

    return Ret.success(
        "获取成功",
        data={
            "total": total,
            "items": user_list,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/{user_id}", summary="获取用户详情")
async def get_user(
    user_id: int,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """获取用户详情"""
    if _platform_admin.perm_level < Role.Admin:
        raise PermissionDeniedError

    user = await DBUser.get_or_none(id=user_id)
    if not user:
        return Ret.fail("用户不存在")

    return Ret.success(
        "获取成功",
        data={
            "id": user.id,
            "username": user.username,
            "adapter_key": user.adapter_key,
            "platform_userid": user.platform_userid,
            "unique_id": user.unique_id,
            "perm_level": user.perm_level,
            "perm_role": get_perm_role(user.perm_level),
            "login_time": user.login_time,
            "ban_until": user.ban_until,
            "prevent_trigger_until": user.prevent_trigger_until,
            "is_active": user.is_active,
            "is_prevent_trigger": user.is_prevent_trigger,
            "ext_data": user.ext_data,
            "create_time": user.create_time,
            "update_time": user.update_time,
        },
    )


@router.put("/{user_id}", summary="更新用户信息")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """更新用户信息"""
    if _platform_admin.perm_level < Role.Admin:
        raise PermissionDeniedError

    user = await DBUser.get_or_none(id=user_id)
    if not user:
        return Ret.fail("用户不存在")

    # 验证访问密钥
    if user_data.access_key != OsEnv.SUPER_ACCESS_KEY:
        raise UnauthorizedError

    from holo_cortex_zero.services.context_window.manager import context_window_manager

    sanitized_username = context_window_manager._sanitize_sender_name_for_context(
        user.platform_userid,
        user_data.username,
    )
    if sanitized_username != str(user_data.username or "").strip():
        logger.warning(
            "后台更新用户命中受保护昵称清洗: user_id=%s platform_userid=%s raw_username=%r sanitized=%s",
            user.id,
            user.platform_userid,
            user_data.username,
            sanitized_username,
        )
    user.username = sanitized_username
    user.perm_level = user_data.perm_level
    await user.save()

    return Ret.success("更新成功")


class BanUserRequest(BaseModel):
    ban_until: Optional[datetime] = None


@router.post("/{user_id}/ban", summary="封禁/解封用户")
async def ban_user(
    user_id: int,
    ban_data: BanUserRequest,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """封禁/解封用户"""
    if _platform_admin.perm_level < Role.Admin:
        raise PermissionDeniedError

    user = await DBUser.get_or_none(id=user_id)
    if not user:
        return Ret.fail("用户不存在")

    # 类型安全地设置ban_until
    user.ban_until = cast(datetime, ban_data.ban_until)
    await user.save()

    return Ret.success("操作成功")


class PreventTriggerRequest(BaseModel):
    prevent_trigger_until: Optional[datetime] = None


@router.post("/{user_id}/prevent-trigger", summary="设置触发权限")
async def prevent_trigger(
    user_id: int,
    prevent_data: PreventTriggerRequest,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """设置触发权限"""
    if _platform_admin.perm_level < Role.Admin:
        raise PermissionDeniedError

    user = await DBUser.get_or_none(id=user_id)
    if not user:
        return Ret.fail("用户不存在")

    # 类型安全地设置prevent_trigger_until
    user.prevent_trigger_until = cast(datetime, prevent_data.prevent_trigger_until)
    await user.save()

    return Ret.success("操作成功")


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
    user_id: int,
    _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
) -> Ret:
    """删除用户"""
    if _platform_admin.perm_level < Role.Admin:
        raise PermissionDeniedError

    user = await DBUser.get_or_none(id=user_id)
    if not user:
        return Ret.fail("用户不存在")

    await user.delete()
    return Ret.success("删除成功")
