import asyncio
import json
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiodocker
from aiodocker.containers import DockerContainer
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import ONEBOT_ACCESS_TOKEN
from holo_cortex_zero.schemas.errors import AppError, OperationFailedError, ValidationError
from holo_cortex_zero.schemas.i18n import SupportedLang
from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.services.platform_admin import PlatformAdminPrincipal, get_current_active_platform_admin
from holo_cortex_zero.services.platform_admin import require_platform_role
from holo_cortex_zero.services.user.role import Role

router = APIRouter(prefix="/container", tags=["OneBot V11 Container"])


@router.get("/onebot-token")
@require_platform_role(Role.Admin)
async def get_onebot_token(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取 OneBot 访问令牌"""
    if not ONEBOT_ACCESS_TOKEN:
        return Ret.success(data=None, msg="未设置 OneBot 访问令牌")
    return Ret.success(data=ONEBOT_ACCESS_TOKEN, msg="获取 OneBot 访问令牌成功")


@router.get("/napcat-token")
@require_platform_role(Role.Admin)
async def get_napcat_token(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取 NapCat WebUI 访问令牌

    通过读取宿主机上挂载的 NapCat 配置文件来获取 WebUI token。
    配置文件路径: ${DATA_DIR}/napcat_data/napcat/webui.json
    """
    try:
        # 检查容器状态
        try:
            client, container = await get_container_and_client()
            try:
                state = (await container.show())["State"]
            finally:
                await close_docker(client)
            if not state["Running"]:
                return Ret.fail("NapCat 容器未运行")
        except Exception as e:
            logger.warning(f"无法获取容器状态: {e!s}")
            return Ret.fail("无法连接到 NapCat 容器")

        # 构建配置文件路径（从宿主机读取）
        from holo_cortex_zero.core.os_env import OsEnv

        config_file_path = Path(OsEnv.DATA_DIR) / "napcat_data" / "napcat" / "webui.json"

        # 检查文件是否存在
        if not config_file_path.exists():
            logger.error(f"配置文件不存在: {config_file_path}")
            return Ret.fail("配置文件不存在，请确保 NapCat 已完成初始化")

        # 读取配置文件
        try:
            config_text = config_file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"读取配置文件失败: {e!s}")
            return Ret.fail("读取配置文件失败")

        # 解析 JSON 并提取 token
        try:
            config_data = json.loads(config_text)
            token = config_data.get("token")

            if not token:
                return Ret.fail("配置文件中未找到 token 字段")

            return Ret.success(data=token, msg="获取 NapCat WebUI 访问令牌成功")
        except json.JSONDecodeError as e:
            logger.error(f"解析 NapCat 配置文件失败: {e!s}")
            return Ret.fail("配置文件格式错误，请检查 JSON 格式是否正确")

    except Exception as e:
        logger.error(f"获取 NapCat WebUI 令牌失败: {e!s}")
        return Ret.fail(f"获取令牌失败: {e!s}")


async def get_docker() -> aiodocker.Docker:
    """获取 Docker 客户端。"""
    return aiodocker.Docker()


async def close_docker(client: Optional[aiodocker.Docker]) -> None:
    """安全关闭 Docker 客户端，避免 aiohttp connector 泄漏。"""
    if client is None:
        return
    try:
        await client.close()
    except Exception as e:
        logger.warning(f"关闭 Docker 客户端失败，已继续: {e!s}")


async def get_container_and_client() -> tuple[aiodocker.Docker, DockerContainer]:
    """获取 NapCat 容器实例及其 Docker 客户端。"""
    from holo_cortex_zero.adapters.utils import adapter_utils
    from holo_cortex_zero.adapters.onebot_v11.adapter import OnebotV11Adapter

    adapter = adapter_utils.get_typed_adapter("onebot_v11", OnebotV11Adapter)

    if not adapter.config.NAPCAT_CONTAINER_NAME:
        raise ValidationError(reason="未设置 NapCat 容器名称")

    client = await get_docker()
    try:
        container = await client.containers.get(adapter.config.NAPCAT_CONTAINER_NAME)
        return client, container
    except Exception as e:
        await close_docker(client)
        logger.error(f"获取容器失败: {e!s}")
        raise OperationFailedError(operation="获取 NapCat 容器", detail=str(e)) from e


@router.get("/status")
@require_platform_role(Role.Admin)
async def get_status(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取容器状态"""
    try:
        client, container = await get_container_and_client()
        try:
            state = (await container.show())["State"]
        finally:
            await close_docker(client)
        return Ret.success(
            data={
                "running": state["Running"],
                "started_at": state["StartedAt"],
            },
            msg="获取容器状态成功",
        )
    except AppError as e:
        return Ret.fail(e.get_message(SupportedLang.ZH_CN))
    except Exception as e:
        logger.error(f"获取状态失败: {e!s}")
        return Ret.fail(str(e))


@router.get("/logs")
@require_platform_role(Role.Admin)
async def get_logs(tail: Optional[int] = 100, _platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> Ret:
    """获取最近的容器日志"""
    try:
        client, container = await get_container_and_client()
        try:
            logs = await container.log(stdout=True, stderr=True, tail=tail)
        finally:
            await close_docker(client)
        return Ret.success(data=logs, msg="获取日志成功")
    except AppError as e:
        return Ret.fail(e.get_message(SupportedLang.ZH_CN))
    except Exception as e:
        logger.error(f"获取日志失败: {e!s}")
        return Ret.fail(str(e))


@router.get("/logs/stream")
@require_platform_role(Role.Admin)
async def stream_logs(_platform_admin: PlatformAdminPrincipal = Depends(get_current_active_platform_admin)) -> EventSourceResponse:
    """实时日志流"""
    try:

        async def generate() -> AsyncGenerator[str, None]:
            client: Optional[aiodocker.Docker] = None
            log_stream = None
            try:
                client, container = await get_container_and_client()
                initial_logs = await container.log(stdout=True, stderr=True, tail=100, timestamps=False)
                init_time = time.time()
                for log in initial_logs:
                    yield log
                    await asyncio.sleep(0.01)

                log_stream = container.log(stdout=True, stderr=True, follow=True, since=int(init_time), timestamps=False)
                async for log in log_stream:
                    yield log
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                logger.info("OneBot 容器日志流已断开，开始清理 Docker 客户端")
                raise
            except Exception as e:
                logger.error(f"日志流异常: {e!s}")
                raise
            finally:
                try:
                    if log_stream is not None:
                        aclose = getattr(log_stream, "aclose", None)
                        if callable(aclose):
                            await aclose()
                except Exception as e:
                    logger.warning(f"关闭日志流失败，已继续: {e!s}")
                await close_docker(client)

        return EventSourceResponse(generate())
    except Exception as e:
        logger.error(f"日志流异常: {e!s}")
        raise OperationFailedError(operation="建立 OneBot 容器日志流", detail=str(e)) from e
