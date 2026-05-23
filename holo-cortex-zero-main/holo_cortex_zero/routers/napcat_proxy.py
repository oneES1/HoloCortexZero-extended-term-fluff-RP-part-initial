import re
from typing import Iterable

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from holo_cortex_zero.core.logger import logger

router = APIRouter(tags=["NapCat Proxy"])

_DEFAULT_NAPCAT_BASE_URL = "http://hcz_napcat:65535"
_PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=5.0)
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_REWRITE_CONTENT_TYPES = (
    "text/html",
    "text/css",
    "application/javascript",
    "text/javascript",
    "application/json",
)


def _napcat_base_url() -> str:
    try:
        from holo_cortex_zero.adapters.onebot_v11.adapter import OnebotV11Adapter
        from holo_cortex_zero.adapters.utils import adapter_utils

        adapter = adapter_utils.get_typed_adapter("onebot_v11", OnebotV11Adapter)
        configured = str(getattr(adapter.config, "NAPCAT_PROXY_BASE_URL", "") or "").strip()
        if configured:
            return configured.rstrip("/")
    except Exception as e:
        logger.warning(f"读取 NapCat 内部代理地址失败，使用默认值: {e!s}")
    return _DEFAULT_NAPCAT_BASE_URL


def _forward_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for key, value in headers:
        lower_key = key.lower()
        if lower_key in _HOP_BY_HOP_HEADERS or lower_key in {"host", "content-length", "accept-encoding"}:
            continue
        forwarded[key] = value
    return forwarded


def _response_headers(headers: httpx.Headers, *, rewritten: bool) -> dict[str, str]:
    response_headers: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in _HOP_BY_HOP_HEADERS:
            continue
        if lower_key == "content-length":
            continue
        # 主干：httpx 读取 upstream.content 时会自动解压 gzip/br 等编码，反代返回明文 body 时不能透传上游编码头。
        if lower_key == "content-encoding":
            continue
        if lower_key == "location":
            response_headers[key] = _rewrite_location(value)
            continue
        response_headers[key] = value
    return response_headers


def _map_path(path: str) -> str:
    if not path:
        return "/webui/"
    if path.startswith(("webui/", "api/", "files/")):
        return f"/{path}"
    if path in {"qq_login", "web_login"}:
        return "/webui/"
    return f"/webui/{path}"


def _rewrite_location(value: str) -> str:
    if value.startswith("/webui/"):
        return f"/napcat{value}"
    if value.startswith("/api"):
        return f"/napcat{value}"
    if value.startswith("/files/"):
        return f"/napcat{value}"
    return value


def _should_rewrite(content_type: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized in _REWRITE_CONTENT_TYPES


def _rewrite_body(body: bytes, content_type: str) -> tuple[bytes, bool]:
    if not body or not _should_rewrite(content_type):
        return body, False

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body, False

    rewritten = re.sub(r"(?<!/napcat)/webui/", "/napcat/webui/", text)
    rewritten = re.sub(r"(?<!/napcat)/files/", "/napcat/files/", rewritten)
    rewritten = re.sub(r"(?<!/napcat)/api(?=([/?#\"'`\s]|$))", "/napcat/api", rewritten)
    if rewritten == text:
        return body, False
    return rewritten.encode("utf-8"), True


async def _proxy_request(request: Request, target_path: str) -> Response:
    base_url = _napcat_base_url()
    mapped_path = _map_path(target_path)
    target_url = httpx.URL(f"{base_url}{mapped_path}")
    if request.url.query:
        target_url = target_url.copy_with(query=request.url.query.encode("utf-8"))
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=_PROXY_TIMEOUT, trust_env=False, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target_url,
                headers=_forward_headers(request.headers.items()),
                content=body,
            )
    except httpx.RequestError as e:
        logger.warning(f"NapCat 内置反代请求失败: method={request.method} url={target_url} error={e!s}")
        return Response("NapCat service is unavailable", status_code=502, media_type="text/plain")

    content_type = upstream.headers.get("content-type", "")
    body_content, rewritten = _rewrite_body(upstream.content, content_type)
    return Response(
        content=body_content,
        status_code=upstream.status_code,
        headers=_response_headers(upstream.headers, rewritten=rewritten),
        media_type=content_type or None,
    )


@router.api_route("/napcat", methods=["GET", "HEAD"], include_in_schema=False)
async def redirect_napcat_root() -> RedirectResponse:
    return RedirectResponse(url="/napcat/webui/", status_code=302)


@router.api_route(
    "/napcat/{target_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def proxy_napcat(request: Request, target_path: str) -> Response:
    return await _proxy_request(request, target_path)


@router.api_route("/qq_login", methods=["GET", "POST", "HEAD"], include_in_schema=False)
async def proxy_qq_login(request: Request) -> Response:
    return await _proxy_request(request, "qq_login")


@router.api_route("/web_login", methods=["GET", "POST", "HEAD"], include_in_schema=False)
async def proxy_web_login(request: Request) -> Response:
    return await _proxy_request(request, "web_login")
