from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger

_BOOTSTRAPPED = False


def bootstrap_application() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    from nonebot import get_app, get_driver

    from holo_cortex_zero.adapters import cleanup_adapters, init_adapters
    from holo_cortex_zero.core.args import Args
    from holo_cortex_zero.core.database import init_db
    from holo_cortex_zero.routers import mount_api_routes, mount_middlewares
    from holo_cortex_zero.services.file_system.upload_cleanup import upload_cleanup_service
    from holo_cortex_zero.services.festival_service import festival_service
    from holo_cortex_zero.services.timer_service import timer_service

    # 后端主入口显式执行启动装配；普通业务模块导入不再触发路由与适配器加载。
    app = get_app()
    mount_middlewares(app)
    mount_api_routes(app)


    @get_driver().on_startup
    async def on_startup():
        # 启动时不再挂载主路由，它们已在启动前挂载完毕
        app = get_app()

        # 初始化数据库与适配器
        await init_db()
        await init_adapters(app)

        await timer_service.start()
        logger.info("Timer service initialized")

        await upload_cleanup_service.start()
        logger.info("Upload cleanup service initialized")

        # 初始化节日提醒
        await festival_service.init_festivals()
        logger.info("Festival service initialized")

        logger.info("Legacy container execution runtime retired; skip legacy startup")

        # 初始化新架构（上下文窗口 + tool 注册）
        try:
            from holo_cortex_zero.services.init_new_arch import init_new_architecture
            await init_new_architecture()
        except Exception as e:
            logger.exception(f"新架构初始化失败: {e}")


    @get_driver().on_shutdown
    async def on_shutdown():
        await upload_cleanup_service.stop()
        await timer_service.stop()
        await cleanup_adapters(get_app())

        logger.info("Legacy container execution runtime retired; skip legacy shutdown")
        logger.info("Timer service stopped")

    _BOOTSTRAPPED = True

    if Args.LOAD_TEST:
        logger.success("启动自检通过")
        exit(0)
