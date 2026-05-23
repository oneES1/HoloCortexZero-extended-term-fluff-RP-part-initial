from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Optional

from fastapi import Depends, Request
from jose import JWTError, jwt

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.schemas.admin import AdminLogin, AdminToken
from holo_cortex_zero.schemas.errors import InvalidCredentialsError, PermissionDeniedError, ValidationError
from holo_cortex_zero.services.user.role import Role

ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60


@dataclass(frozen=True)
class PlatformAdminPrincipal:
    """WebUI 平台管理员运行时主体，不对应数据库用户行。"""

    username: str
    perm_level: Role = Role.Admin
    is_active: bool = True


def create_admin_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.utcnow() + (
        expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(
        {"exp": expire, "sub": str(subject)},
        OsEnv.JWT_SECRET_KEY,
        algorithm=OsEnv.ENCRYPT_ALGORITHM,
    )


async def admin_login(data: AdminLogin) -> AdminToken:
    if not OsEnv.ADMIN_PASSWORD:
        logger.warning("WebUI 管理员密码未配置，拒绝登录")
        raise InvalidCredentialsError
    if data.username != OsEnv.ADMIN_USERNAME or data.password != OsEnv.ADMIN_PASSWORD:
        logger.info("WebUI 管理员登录校验失败: username=%s", data.username)
        raise InvalidCredentialsError

    logger.info("WebUI 管理员 %s 登录成功", OsEnv.ADMIN_USERNAME)
    return AdminToken(
        access_token=create_admin_access_token(OsEnv.ADMIN_USERNAME),
        token_type="bearer",
    )


async def get_current_platform_admin(
    request: Request,
    token: Optional[str] = None,
) -> PlatformAdminPrincipal:
    try:
        url_token = request.query_params.get("token")
        if url_token:
            if url_token.startswith("Bearer "):
                url_token = url_token.split(" ")[1]
            token = url_token
        elif not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            else:
                logger.debug("No valid token found in header")
                raise InvalidCredentialsError

        if not token:
            logger.debug("No token found in URL or header")
            raise InvalidCredentialsError

        payload = jwt.decode(token, OsEnv.JWT_SECRET_KEY, algorithms=[OsEnv.ENCRYPT_ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise InvalidCredentialsError
    except JWTError as e:
        logger.info(f"JWT validation failed: {e!s}")
        raise InvalidCredentialsError from e

    if username != OsEnv.ADMIN_USERNAME:
        logger.debug("Reject non-admin WebUI token subject: %s", username)
        raise InvalidCredentialsError
    return PlatformAdminPrincipal(username=OsEnv.ADMIN_USERNAME)


async def get_current_active_platform_admin(
    principal: PlatformAdminPrincipal = Depends(get_current_platform_admin),
) -> PlatformAdminPrincipal:
    if not principal.is_active:
        raise ValidationError(reason="Inactive platform admin")
    return principal


def require_platform_role(min_role: Role) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            *args,
            _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin),
            **kwargs,
        ):
            if _platform_admin.perm_level < min_role:
                raise PermissionDeniedError
            return await func(*args, _platform_admin=_platform_admin, **kwargs)

        return wrapper

    return decorator
