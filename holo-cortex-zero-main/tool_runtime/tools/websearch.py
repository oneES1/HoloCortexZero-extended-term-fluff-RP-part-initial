from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

from tool_runtime.host import ToolHostBridge
from tool_runtime.result import ToolOutcome, ToolPart


TOOL_ID = "websearch"
DISPLAY_NAME = "websearch"
DESCRIPTION = "使用 websearch 进行联网搜索，返回 Tavily Search 的文字摘要与来源链接"
PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "搜索词，可带自然语言或 site: 语法"},
    },
    "required": ["query"],
}

_MAX_RETURN_RESULTS = 30
_DEFAULT_PER_CALL_MAX_RESULTS = 20
_TAVILY_KEY_HELP = """Tavily API Key 获取步骤：
1. 打开 https://app.tavily.com/ 并注册或登录账号。
2. 进入 Dashboard 后，找到 API Keys 页面。
3. 点击创建或复制已有 Key，得到一串以 tvly- 开头的密钥。
4. 回到这里，把密钥粘贴到 Tavily API Key。
5. Tavily API Host 保持 https://api.tavily.com 即可。
6. 保存后，让 Bot 试一句“搜索今天北京天气新闻”，能返回来源链接就说明配置成功。

注意：API Key 是密钥，不要发到群里、不要写进公开仓库。"""

_TAVILY_KEY_HELP_EN = """How to get a Tavily API Key:
1. Open https://app.tavily.com/ and register or log in.
2. Go to the Dashboard and find the API Keys page.
3. Click Create or copy an existing Key to get a secret starting with tvly-.
4. Paste the key into the Tavily API Key field here.
5. Keep Tavily API Host as https://api.tavily.com.
6. Save and ask the bot to try “search today's Beijing weather news”; if source links are returned, the config is working.

Note: The API Key is a secret. Do not share it in groups or commit it to public repos."""


class WebSearchConfig(BaseModel):
    API_HOST: str = Field(
        default="https://api.tavily.com",
        title="Tavily API Host",
        json_schema_extra={"i18n_title": {"zh-CN": "Tavily API Host", "en-US": "Tavily API Host"}},
    )
    TAVILY_API_KEY: str = Field(
        default="",
        title="Tavily API Key",
        json_schema_extra={
            "help_label": "获取 Key 指南",
            "i18n_help_label": {"zh-CN": "获取 Key 指南", "en-US": "Get Key Guide"},
            "help_text": _TAVILY_KEY_HELP,
            "is_secret": True,
            "i18n_title": {"zh-CN": "Tavily API Key", "en-US": "Tavily API Key"},
            "i18n_help_text": {"zh-CN": _TAVILY_KEY_HELP, "en-US": _TAVILY_KEY_HELP_EN},
        },
    )
    SEARCH_DEPTH: str = Field(
        default="advanced",
        title="搜索质量",
        json_schema_extra={"i18n_title": {"zh-CN": "搜索质量", "en-US": "Search Quality"}},
    )
    TOPIC: str = Field(
        default="general",
        title="搜索主题",
        json_schema_extra={"i18n_title": {"zh-CN": "搜索主题", "en-US": "Search Topic"}},
    )
    TIME_RANGE: str = Field(
        default="",
        title="时间范围",
        json_schema_extra={"i18n_title": {"zh-CN": "时间范围", "en-US": "Time Range"}},
    )
    RESULT_COUNT: int = Field(
        default=10,
        title="返回条数",
        json_schema_extra={"i18n_title": {"zh-CN": "返回条数", "en-US": "Result Count"}},
    )
    PER_CALL_MAX_RESULTS: int = Field(
        default=_DEFAULT_PER_CALL_MAX_RESULTS,
        title="单次请求最大条数",
        json_schema_extra={"i18n_title": {"zh-CN": "单次请求最大条数", "en-US": "Max Results Per Call"}},
    )
    ALLOW_MULTI_CALLS: bool = Field(
        default=True,
        title="允许多次请求",
        json_schema_extra={"i18n_title": {"zh-CN": "允许多次请求", "en-US": "Allow Multiple Calls"}},
    )
    CHUNKS_PER_SOURCE: int = Field(
        default=3,
        title="每个来源的 snippet 数量",
        json_schema_extra={"i18n_title": {"zh-CN": "每个来源的 snippet 数量", "en-US": "Snippets Per Source"}},
    )
    SNIPPET_MAX_CHARS: int = Field(
        default=500,
        title="摘要最大长度",
        json_schema_extra={"i18n_title": {"zh-CN": "摘要最大长度", "en-US": "Max Snippet Length"}},
    )
    INCLUDE_ANSWER: bool = Field(
        default=False,
        title="包含 Answer",
        json_schema_extra={"i18n_title": {"zh-CN": "包含 Answer", "en-US": "Include Answer"}},
    )
    INCLUDE_USAGE: bool = Field(
        default=False,
        title="包含 Usage",
        json_schema_extra={"i18n_title": {"zh-CN": "包含 Usage", "en-US": "Include Usage"}},
    )
    REQUEST_TIMEOUT_SEC: float = Field(
        default=30.0,
        title="请求超时",
        json_schema_extra={"i18n_title": {"zh-CN": "请求超时", "en-US": "Request Timeout"}},
    )


CONFIG_MODEL = WebSearchConfig


def _clip_text(text: str, *, max_chars: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if max_chars <= 0 or len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[:max_chars].rstrip()}..."


def _extract_domain(url: str) -> str:
    try:
        return str(urlparse(url).hostname or "").strip().lower()
    except Exception:
        return ""


def _normalize_api_host(host: str) -> str:
    normalized = str(host or "").strip().rstrip("/")
    if not normalized:
        return "https://api.tavily.com"
    if normalized.startswith(("http://", "https://")):
        return normalized
    return f"https://{normalized}"


def _text_outcome(text: str, *, is_error: bool, trace_summary: str) -> ToolOutcome:
    return ToolOutcome(
        parts=[
            ToolPart(
                type="text",
                text=text,
                meta={"source": "tool", "tool_id": TOOL_ID, "inject_role": "tool"},
            ),
        ],
        is_error=is_error,
        history_role="tool",
        trace_title=f"Tool | {TOOL_ID}",
        trace_summary=trace_summary,
    )


def _format_response(query: str, response: dict[str, Any], *, limit: int, snippet_max_chars: int) -> str:
    results = response.get("results") or []
    if not isinstance(results, list) or not results:
        return f"未能找到与“{query}”相关的结果。"

    lines = [f"搜索词：{query}", ""]
    emitted = 0
    for item in results:
        if emitted >= limit or not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip() or "无标题"
        url = str(item.get("url") or "").strip() or "无链接"
        content = _clip_text(str(item.get("content") or "").strip() or "无摘要", max_chars=snippet_max_chars)
        emitted += 1
        lines.append(f"{emitted}. {title}\n   链接: {url}\n   摘要: {content}")

    answer = str(response.get("answer") or "").strip()
    if answer:
        lines.extend(["", "Answer:", _clip_text(answer, max_chars=max(2000, snippet_max_chars * 3))])

    usage = response.get("usage")
    if usage:
        lines.extend(["", f"Usage: {usage}"])
    return "\n".join(lines).strip()


async def _call_tavily_once(
    *,
    tool_host: ToolHostBridge,
    config: WebSearchConfig,
    query: str,
    depth: str,
    topic: str,
    time_range: str,
    include_answer: bool,
    include_usage: bool,
    chunks_per_source: int,
    max_results: int,
    exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "api_key": config.TAVILY_API_KEY,
        "query": query,
        "search_depth": depth,
        "max_results": int(max_results),
        "topic": topic,
        "time_range": time_range or None,
        "include_answer": bool(include_answer),
        "include_raw_content": False,
        "include_images": False,
        "include_image_descriptions": False,
        "include_favicon": False,
        "include_usage": bool(include_usage),
        "exclude_domains": exclude_domains or None,
    }
    if depth == "advanced":
        payload["chunks_per_source"] = int(chunks_per_source)
    payload = {key: value for key, value in payload.items() if value is not None}

    response = await tool_host.http_request(
        method="POST",
        url=f"{_normalize_api_host(config.API_HOST)}/search",
        json=payload,
        timeout=float(config.REQUEST_TIMEOUT_SEC),
    )
    return response.json() if isinstance(response.json(), dict) else {}


async def _search_merged(
    *,
    tool_host: ToolHostBridge,
    config: WebSearchConfig,
    query: str,
    want: int,
    depth: str,
    topic: str,
    time_range: str,
    include_answer: bool,
) -> dict[str, Any]:
    chunks_per_source = min(max(int(config.CHUNKS_PER_SOURCE or 1), 1), 3)
    per_call_limit = min(max(int(config.PER_CALL_MAX_RESULTS or _DEFAULT_PER_CALL_MAX_RESULTS), 1), _MAX_RETURN_RESULTS)
    include_usage = bool(config.INCLUDE_USAGE)

    first = await _call_tavily_once(
        tool_host=tool_host,
        config=config,
        query=query,
        depth=depth,
        topic=topic,
        time_range=time_range,
        include_answer=include_answer,
        include_usage=include_usage,
        chunks_per_source=chunks_per_source,
        max_results=min(want, per_call_limit),
    )

    merged: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in first.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        merged.append(item)
        if len(merged) >= want:
            break

    if len(merged) >= want or want <= per_call_limit or not config.ALLOW_MULTI_CALLS:
        first["results"] = merged[:want]
        return first

    exclude_domains: list[str] = []
    for url in seen_urls:
        domain = _extract_domain(url)
        if domain and domain not in exclude_domains:
            exclude_domains.append(domain)
        if len(exclude_domains) >= 150:
            break

    remaining = min(int(want - len(merged)), per_call_limit)
    second = await _call_tavily_once(
        tool_host=tool_host,
        config=config,
        query=query,
        depth=depth,
        topic=topic,
        time_range=time_range,
        include_answer=False,
        include_usage=include_usage,
        chunks_per_source=chunks_per_source,
        max_results=remaining,
        exclude_domains=exclude_domains or None,
    )

    for item in second.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        merged.append(item)
        if len(merged) >= want:
            break

    first["results"] = merged[:want]
    if second.get("error"):
        first["merge_error"] = second.get("error")
    return first


async def websearch(
    query: str,
    tool_host: ToolHostBridge | None = None,
    tool_config: WebSearchConfig | None = None,
) -> ToolOutcome:
    config = tool_config or WebSearchConfig()
    normalized_query = str(query or "").strip()
    if tool_host is None:
        return _text_outcome("websearch Tool 缺少宿主桥接。", is_error=True, trace_summary="missing_host")
    if not normalized_query:
        return _text_outcome("请提供搜索词。", is_error=True, trace_summary="bad_args")
    if not str(config.TAVILY_API_KEY or "").strip():
        return _text_outcome("未配置 Tavily API Key。", is_error=True, trace_summary="missing_api_key")

    want = max(1, min(int(config.RESULT_COUNT), _MAX_RETURN_RESULTS))
    depth = str(config.SEARCH_DEPTH or "advanced").strip() or "advanced"
    resolved_topic = str(config.TOPIC or "general").strip() or "general"
    resolved_time_range = str(config.TIME_RANGE or "").strip()
    resolved_include_answer = bool(config.INCLUDE_ANSWER)

    await tool_host.log(
        "info",
        "websearch tool start",
        query=normalized_query,
        want=want,
        depth=depth,
        topic=resolved_topic,
        time_range=resolved_time_range,
    )

    try:
        response = await _search_merged(
            tool_host=tool_host,
            config=config,
            query=normalized_query,
            want=want,
            depth=depth,
            topic=resolved_topic,
            time_range=resolved_time_range,
            include_answer=resolved_include_answer,
        )
        if response.get("error"):
            return _text_outcome(str(response.get("error")), is_error=True, trace_summary="provider_error")

        text = _format_response(
            normalized_query,
            response,
            limit=want,
            snippet_max_chars=int(config.SNIPPET_MAX_CHARS),
        )
        if response.get("merge_error"):
            text = f"{text}\n\n（补齐结果时发生异常：{response.get('merge_error')}）"
        await tool_host.log("info", "websearch tool success", query=normalized_query, result_count=want)
        return _text_outcome(text, is_error=False, trace_summary=f"websearch:{normalized_query}")
    except httpx.HTTPStatusError as exc:
        body_preview = ""
        try:
            body_preview = exc.response.text[:300]
        except Exception:
            body_preview = ""
        await tool_host.log(
            "error",
            "websearch tool http error",
            query=normalized_query,
            status_code=exc.response.status_code,
            body=body_preview,
        )
        return _text_outcome(
            f"联网搜索失败（HTTP {exc.response.status_code}）。",
            is_error=True,
            trace_summary=f"http_{exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        await tool_host.log("error", "websearch tool request error", query=normalized_query, error=str(exc))
        return _text_outcome("联网搜索请求失败，请稍后再试。", is_error=True, trace_summary="request_error")
    except Exception as exc:
        await tool_host.log("error", "websearch tool unexpected error", query=normalized_query, error=str(exc))
        return _text_outcome(f"搜索时遇到未知错误：{exc}", is_error=True, trace_summary="unexpected_error")
