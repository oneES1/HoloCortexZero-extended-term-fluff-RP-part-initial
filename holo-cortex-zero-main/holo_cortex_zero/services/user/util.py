from datetime import datetime

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.models.db_user import DBUser
from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.schemas.user import (
    UserCreate,
)
from holo_cortex_zero.services.user.role import Role


async def user_register(data: UserCreate) -> Ret:
    from holo_cortex_zero.services.context_window.manager import context_window_manager

    sanitized_username = context_window_manager._sanitize_sender_name_for_context(
        data.platform_userid,
        data.username,
    )
    if sanitized_username != str(data.username or "").strip():
        logger.warning(
            "用户注册命中受保护昵称清洗: adapter=%s platform_userid=%s raw_username=%r sanitized=%s",
            data.adapter_key,
            data.platform_userid,
            data.username,
            sanitized_username,
        )
    logger.info(f"正在注册用户 {sanitized_username} ...")
    if sanitized_username == OsEnv.ADMIN_USERNAME:
        return Ret.fail("注册失败，管理员保留用户名无法注册")
    if await DBUser.get_or_none(adapter_key=data.adapter_key, platform_userid=data.platform_userid):
        return Ret.fail("注册失败，用户已存在")
    try:
        await DBUser.create(
            username=sanitized_username,
            adapter_key=data.adapter_key,
            platform_userid=data.platform_userid,
            perm_level=Role.User,
            login_time=datetime.now(),
        )
        return Ret.success("注册成功")
    except Exception as e:
        logger.error(f"注册用户时发生错误: {e}")
        return Ret.fail("注册失败，请稍后再试。")
