import contextlib
import os
import secrets
import subprocess
from pathlib import Path

from .core_utils import OsEnvTypes


def _detect_workspace_root() -> str:
    configured = str(os.environ.get('HCZ_WORKSPACE_ROOT') or os.environ.get('WORKSPACE_ROOT') or '').strip()
    if configured:
        return configured
    workspace_mount = Path('/workspace')
    if workspace_mount.exists():
        return str(workspace_mount)
    for ancestor in Path(__file__).resolve().parents:
        if (ancestor / 'docker-compose.yml').exists() and (ancestor / 'holo-cortex-zero-main').exists():
            return str(ancestor)
    return str(Path.cwd())


class OsEnv:
    """系统变量"""

    """实例名称"""
    INSTANCE_NAME: str = OsEnvTypes.Str("INSTANCE_NAME", default="")

    """数据目录"""
    DATA_DIR: str = OsEnvTypes.Str("DATA_DIR", default="./data")

    """工作区根目录"""
    WORKSPACE_ROOT: str = OsEnvTypes.Str("WORKSPACE_ROOT", default=_detect_workspace_root)

    """Postgres 数据库配置"""
    USE_ENV_DATABASE: str = OsEnvTypes.Str("USE_ENV_DATABASE", default="false")
    POSTGRES_HOST: str = OsEnvTypes.Str("POSTGRES_HOST", default="localhost")
    POSTGRES_PORT: int = OsEnvTypes.Int("POSTGRES_PORT", default=5432)
    POSTGRES_USER: str = OsEnvTypes.Str("POSTGRES_USER", default="holo_cortex_zero")
    POSTGRES_PASSWORD: str = OsEnvTypes.Str("POSTGRES_PASSWORD", default="holo_cortex_zero")
    POSTGRES_DATABASE: str = OsEnvTypes.Str("POSTGRES_DATABASE", default="holo_cortex_zero")

    """Qdrant 数据库配置"""
    USE_ENV_QDRANT: str = OsEnvTypes.Str("USE_ENV_QDRANT", default="false")
    QDRANT_URL: str = OsEnvTypes.Str("QDRANT_URL", default="http://localhost:6333")
    QDRANT_API_KEY: str = OsEnvTypes.Str("QDRANT_API_KEY", default="")

    """JWT 配置"""
    JWT_SECRET_KEY: str = OsEnvTypes.Str("JWT_SECRET_KEY", default=f"secret:{secrets.token_urlsafe(32)}")
    SUPER_ACCESS_KEY: str = OsEnvTypes.Str("SUPER_ACCESS_KEY", default=lambda: os.urandom(32).hex())
    ENCRYPT_ALGORITHM: str = OsEnvTypes.Str("ENCRYPT_ALGORITHM", default="HS256")

    """RPC 配置"""
    RPC_SECRET_KEY: str = OsEnvTypes.Str("RPC_SECRET_KEY", default=f"rpc:{secrets.token_urlsafe(32)}")

    """Webhook 配置"""
    WEBHOOK_SECRET_KEY: str = OsEnvTypes.Str("WEBHOOK_SECRET_KEY", default=f"webhook:{secrets.token_urlsafe(32)}")

    """其他配置"""
    RUN_IN_DOCKER: bool = OsEnvTypes.Bool("RUN_IN_DOCKER")

    """暴露端口"""
    EXPOSE_PORT: int = OsEnvTypes.Int("EXPOSE_PORT", default=20261)

    """前端资源目录"""
    STATIC_DIR: str = OsEnvTypes.Str("STATIC_DIR", default="./static")

    """WebUI 管理员密码"""
    ADMIN_PASSWORD: str = OsEnvTypes.Str("ADMIN_PASSWORD", default="123456")
    """WebUI 管理员用户名"""
    ADMIN_USERNAME: str = OsEnvTypes.Str("ADMIN_USERNAME", default="admin")

    """OPENAPI 配置"""
    ENABLE_OPENAPI_DOCS: bool = OsEnvTypes.Bool("ENABLE_OPENAPI_DOCS")


APP_SYSTEM_DIR: str = OsEnv.DATA_DIR + "/system"  # 系统目录
USER_UPLOAD_DIR: str = OsEnv.DATA_DIR + "/uploads"  # 用户资源上传目录
PROMPT_LOG_DIR: str = OsEnv.DATA_DIR + "/logs/prompts"  # 提示词日志目录
PROMPT_ERROR_LOG_DIR: str = OsEnv.DATA_DIR + "/logs/prompts_error"  # 提示词错误日志目录
APP_LOG_DIR: str = OsEnv.DATA_DIR + "/logs/app"  # 应用日志目录
MEMORY_LOG_DIR: str = OsEnv.DATA_DIR + "/logs/memory"  # 记忆 payload 日志目录
NAPCAT_TEMPFILE_DIR: str = OsEnv.DATA_DIR + "/napcat_data/QQ/NapCat/temp"  # NapCat 临时文件目录
NAPCAT_ONEBOT_ADAPTER_DIR: str = OsEnv.DATA_DIR + "/napcat_data/napcat"  # NapCat OneBot 适配器目录
ONEBOT_ACCESS_TOKEN: str = os.getenv("ONEBOT_ACCESS_TOKEN", "")


# 设置运行期目录及其子目录权限
with contextlib.suppress(Exception):
    Path(USER_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(APP_LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(PROMPT_LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(PROMPT_ERROR_LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(MEMORY_LOG_DIR).mkdir(parents=True, exist_ok=True)
    subprocess.run(["chmod", "-R", "755", USER_UPLOAD_DIR], check=True)
    print(f"Set permission of {USER_UPLOAD_DIR} to 755")
