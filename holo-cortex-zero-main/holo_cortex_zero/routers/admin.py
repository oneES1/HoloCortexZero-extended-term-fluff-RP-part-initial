from datetime import datetime, timedelta

from fastapi import APIRouter

from holo_cortex_zero import logger
from holo_cortex_zero.schemas.errors import TooManyAttemptsError
from holo_cortex_zero.schemas.admin import AdminLogin, AdminLoginRet
from holo_cortex_zero.services.platform_admin import admin_login

router = APIRouter(prefix="/admin", tags=["PlatformAdmin"])

# 登录尝试记录：{admin_name: {attempts: int, last_attempt: datetime}}
login_attempts = {}
# 最大尝试次数和锁定时间
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION = timedelta(minutes=72000)


# 清理过期的登录尝试记录
def clean_expired_attempts():
    now = datetime.now()
    expired_admins = []
    for username, data in login_attempts.items():
        if data["last_attempt"] + LOCKOUT_DURATION < now:
            expired_admins.append(username)
    for username in expired_admins:
        login_attempts.pop(username)


@router.post("/login", summary="WebUI 平台管理员登录")
async def login(req_data: AdminLogin) -> AdminLoginRet:
    clean_expired_attempts()

    if req_data.username in login_attempts:
        admin_attempts = login_attempts[req_data.username]
        if admin_attempts["attempts"] >= MAX_LOGIN_ATTEMPTS:
            now = datetime.now()
            lock_expires = admin_attempts["last_attempt"] + LOCKOUT_DURATION
            if now < lock_expires:
                logger.warning(f"平台管理员 {req_data.username} 尝试登录次数过多，账户被锁定到 {lock_expires}")
                raise TooManyAttemptsError
            login_attempts.pop(req_data.username)

    try:
        login_token = await admin_login(req_data)
        if req_data.username in login_attempts:
            login_attempts.pop(req_data.username)
        return AdminLoginRet(
            access_token=login_token.access_token,
            token_type=login_token.token_type,
        )
    except Exception:
        now = datetime.now()
        if req_data.username not in login_attempts:
            login_attempts[req_data.username] = {"attempts": 1, "last_attempt": now}
        else:
            login_attempts[req_data.username]["attempts"] += 1
            login_attempts[req_data.username]["last_attempt"] = now
        logger.warning(
            f"平台管理员 {req_data.username} 登录失败，当前尝试次数: {login_attempts[req_data.username]['attempts']}"
        )
        raise
