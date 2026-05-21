from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from holo_cortex_zero.adapters import load_adapters_api
from holo_cortex_zero.core.args import Args
from holo_cortex_zero.core.exception_handlers import register_exception_handlers
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.core.runtime_identity import get_bot_persona_display_name
from holo_cortex_zero.schemas.message import Ret
from holo_cortex_zero.tools.common_util import get_app_version

from .adapters import router as adapters_router
from .chat_channel import router as chat_channel_router
from .config import router as config_router
from .dashboard import router as dashboard_router
from .tools import router as tools_router
from .logs import router as logs_router
from .napcat_proxy import router as napcat_proxy_router
from .restart import router as restart_router
from .tool_traces import router as tool_traces_router
from .admin import router as admin_router
from .user_manager import router as user_manager_router



class WebUIStaticFiles(StaticFiles):
    """WebUI 静态文件：仅对 HTML 入口禁缓存，避免浏览器继续引用旧 bundle。"""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        normalized_path = str(path or '').strip().lower()
        content_type = str(response.headers.get('content-type') or '').lower()
        if normalized_path in {'', '.', 'index.html'} or content_type.startswith('text/html'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

# 注意：当前 API 入口统一静态挂载到主应用；扩展运行面已收口为 Tool 管理。


def mount_middlewares(app: FastAPI):
    """挂载中间件和全局处理器"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册统一的全局异常处理器
    # 支持 AppError 业务错误、验证错误、HTTPException 及通用异常
    register_exception_handlers(app)


def mount_api_routes(app: FastAPI):
    """挂载 API 路由"""
    api = APIRouter(prefix="/api")

    api.include_router(admin_router)
    api.include_router(user_manager_router)
    api.include_router(logs_router)
    api.include_router(config_router)
    api.include_router(tools_router)
    api.include_router(tool_traces_router)
    api.include_router(dashboard_router)
    api.include_router(chat_channel_router)
    api.include_router(restart_router)
    api.include_router(adapters_router)
    api.include_router(load_adapters_api())

    @api.get("/health", response_model=Ret, tags=["Health"], summary="健康检查")
    async def _() -> Ret:
        """测试服务是否正常运行"""
        return Ret.success(msg=f"{get_bot_persona_display_name()}（Holo Cortex Zero）Service Running...")

    if Args.DOCS or OsEnv.ENABLE_OPENAPI_DOCS:
        # 挂载 API 文档
        @api.get("/docs", include_in_schema=False)
        async def custom_swagger_ui_html(request: Request):
            return get_swagger_ui_html(
                openapi_url=request.app.openapi_url,
                title=f"{get_bot_persona_display_name()}（Holo Cortex Zero）API",
            )

        # redoc
        @api.get("/redoc", include_in_schema=False)
        async def redoc_html(request: Request):
            return get_redoc_html(
                openapi_url=request.app.openapi_url,
                title=f"{get_bot_persona_display_name()}（Holo Cortex Zero）API",
            )

        @api.get("/openapi.json", include_in_schema=False)
        async def custom_openapi(request: Request):
            """生成并缓存全局 OpenAPI 文档"""
            app_instance = request.app
            # 总是重新生成，以反映动态添加/删除的路由
            openapi_schema = get_openapi(
                title=f"{get_bot_persona_display_name()}（Holo Cortex Zero）API",
                version=get_app_version(),
                routes=app_instance.routes,
                description=f"{get_bot_persona_display_name()}（Holo Cortex Zero）API 文档（包含动态扩展路由）",
            )
            app_instance.openapi_schema = openapi_schema

            # 添加HTTP头，强制浏览器不缓存OpenAPI文档
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
            return JSONResponse(openapi_schema, headers=headers)

    app.include_router(api)
    app.include_router(napcat_proxy_router)

    # 🎯 正确的静态文件挂载方案：/webui + 根路径重定向
    try:
        static_dir = Path(OsEnv.STATIC_DIR)
        if static_dir.exists():
            # 将前端静态文件挂载到 /webui 路径

            app.mount("/webui", WebUIStaticFiles(directory=str(static_dir), html=True), name="webui")
            logger.info(f"✅ 前端静态文件已挂载到 /webui 路径: {static_dir}")

            # 添加根路径重定向到前端界面
            @app.get("/", include_in_schema=False)
            async def redirect_to_webui():
                """根路径重定向到前端界面"""
                return RedirectResponse(url="/webui", status_code=302)

            # 也处理 /index.html 的情况
            @app.get("/index.html", include_in_schema=False)
            async def redirect_index_to_webui():
                """index.html 重定向到前端界面"""
                return RedirectResponse(url="/webui", status_code=302)

            logger.info("✅ 根路径重定向已配置：/ -> /webui/")
    except Exception as e:
        logger.exception(f"❌ 挂载静态文件失败: {e}")

    # 将 OpenAPI 文档生成和 URL 设置移到 app 上，确保全局生效
    app.openapi_url = "/api/openapi.json"
