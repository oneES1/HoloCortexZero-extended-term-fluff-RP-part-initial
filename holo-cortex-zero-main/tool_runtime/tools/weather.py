from __future__ import annotations

import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from tool_runtime.host import ToolHostBridge
from tool_runtime.result import ToolOutcome, ToolPart


TOOL_ID = "weather"
DISPLAY_NAME = "天气查询"
DESCRIPTION = "查询地点的逐小时天气预报"
PARAMETERS = {
    "type": "object",
    "properties": {
        "location": {
            "type": "string",
            "description": "地点名称、城市 ID，或经纬度 `lon,lat`",
        },
        "adm": {
            "type": "string",
            "description": "可留空，行政区补充",
        },
        "geo_range": {
            "type": "string",
            "description": "可留空，默认中国",
        },
    },
    "required": ["location"],
}

_RE_COORD = re.compile(r"^\s*-?\d{1,3}(\.\d+)?\s*,\s*-?\d{1,2}(\.\d+)?\s*$")
_QWEATHER_KEY_HELP = """QWeather API Key 获取步骤：
1. 打开 https://dev.qweather.com/ 并注册或登录和风天气开发者账号。
2. 进入控制台，先创建 Project；如果已有 Project，可以直接点进去。
3. 在 Project 里进入 Credential / 凭据管理，选择创建 Credential。
4. 类型选择 API KEY；如果页面让你选择订阅或服务，选天气预报和城市搜索能用的免费方案即可。
5. 创建后复制 Key，回到这里粘贴到 API Key。
6. 如果控制台“设置 / API Host”给了你的专属 Host，把 API Host 改成控制台显示的 Host。
7. Geo Host 先保持 https://geoapi.qweather.com，用于城市搜索。
8. 保存后，让 Bot 试一句“查北京天气”，能返回逐小时天气就说明配置成功。

注意：API Key 是密钥，不要发到群里、不要写进公开仓库。"""

_QWEATHER_KEY_HELP_EN = """How to get a QWeather API Key:
1. Open https://dev.qweather.com/ and register or log in to the QWeather developer account.
2. Enter the console and create a Project first; if you already have one, open it directly.
3. In the Project, go to Credential management and choose Create Credential.
4. Select API KEY as the type; if the page asks for a subscription or service, choose the free plan that covers weather forecast and city search.
5. Copy the created key and paste it into the API Key field here.
6. If the console Settings / API Host shows a dedicated host, change API Host to that value.
7. Keep Geo Host as https://geoapi.qweather.com for city search.
8. Save and ask the bot to try “check Beijing weather”; if hourly forecasts are returned, the config is working.

Note: The API Key is a secret. Do not share it in groups or commit it to public repos."""


class WeatherConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    API_HOST: str = Field(
        default="https://devapi.qweather.com",
        title="QWeather API Host",
        json_schema_extra={"i18n_title": {"zh-CN": "QWeather API Host", "en-US": "QWeather API Host"}},
    )
    GEO_HOST: str = Field(
        default="https://geoapi.qweather.com",
        title="QWeather Geo Host",
        json_schema_extra={"i18n_title": {"zh-CN": "QWeather Geo Host", "en-US": "QWeather Geo Host"}},
    )
    API_KEY: str = Field(
        default="",
        title="API Key",
        json_schema_extra={
            "help_label": "获取 Key 指南",
            "i18n_help_label": {"zh-CN": "获取 Key 指南", "en-US": "Get Key Guide"},
            "help_text": _QWEATHER_KEY_HELP,
            "is_secret": True,
            "i18n_title": {"zh-CN": "API Key", "en-US": "API Key"},
            "i18n_help_text": {"zh-CN": _QWEATHER_KEY_HELP, "en-US": _QWEATHER_KEY_HELP_EN},
        },
    )
    GEO_RANGE: str = Field(
        default="cn",
        title="Geo 搜索范围",
        json_schema_extra={"i18n_title": {"zh-CN": "Geo 搜索范围", "en-US": "Geo Search Range"}},
    )
    LANG: str = Field(
        default="zh",
        title="语言",
        json_schema_extra={"i18n_title": {"zh-CN": "语言", "en-US": "Language"}},
    )
    TIMEOUT: int = Field(
        default=10,
        title="请求超时时间",
        json_schema_extra={"i18n_title": {"zh-CN": "请求超时时间", "en-US": "Request Timeout"}},
    )


CONFIG_MODEL = WeatherConfig


def _norm_host(value: str) -> str:
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        return ""
    if normalized.lower().startswith(("http://", "https://")):
        return normalized
    return f"https://{normalized}"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _pick_location(query: str, geo_payload: dict[str, Any]) -> tuple[str, str]:
    locations = geo_payload.get("location") or []
    if not isinstance(locations, list):
        return "", ""

    normalized_query = str(query or "").strip()
    for item in locations:
        if not isinstance(item, dict):
            continue
        loc_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if loc_id and name and name == normalized_query:
            return loc_id, name

    for item in locations:
        if not isinstance(item, dict):
            continue
        loc_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if loc_id and name:
            return loc_id, name
    return "", ""


def _pick_poi_location(query: str, poi_payload: dict[str, Any]) -> tuple[str, str]:
    pois = poi_payload.get("poi") or []
    if not isinstance(pois, list):
        return "", ""

    normalized_query = str(query or "").strip()
    for item in pois:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        lon = str(item.get("lon") or "").strip()
        lat = str(item.get("lat") or "").strip()
        if name == normalized_query and lon and lat:
            return f"{lon},{lat}", name

    for item in pois:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        lon = str(item.get("lon") or "").strip()
        lat = str(item.get("lat") or "").strip()
        if name and lon and lat:
            return f"{lon},{lat}", name
    return "", ""


def _is_no_such_location(exc: httpx.HTTPStatusError) -> bool:
    if exc.response.status_code != 400:
        return False
    try:
        payload = exc.response.json()
    except Exception:
        return False
    payload = _as_dict(payload)
    error = _as_dict(payload.get("error"))
    title = str(error.get("title") or "").strip()
    error_type = str(error.get("type") or "").strip()
    return title == "No Such Location" or error_type.endswith("#no-such-location")


async def _request_json(
    *,
    tool_host: ToolHostBridge,
    url: str,
    params: dict[str, Any],
    api_key: str,
    timeout: int,
    allow_query_fallback: bool = False,
) -> dict[str, Any]:
    headers = {"X-QW-Api-Key": api_key} if api_key else {}
    try:
        response = await tool_host.http_request(
            method="GET",
            url=url,
            params=params,
            headers=headers,
            timeout=float(timeout),
        )
        return _as_dict(response.json())
    except httpx.HTTPStatusError as exc:
        if allow_query_fallback and exc.response.status_code in {401, 403} and api_key and "key" not in params:
            fallback = await tool_host.http_request(
                method="GET",
                url=url,
                params={**params, "key": api_key},
                timeout=float(timeout),
            )
            return _as_dict(fallback.json())
        raise


def _format_hourly_lines(hourly: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in hourly[:24]:
        if not isinstance(item, dict):
            continue
        fx_time = str(item.get("fxTime") or "").strip() or "未知时间"
        temp = str(item.get("temp") or "?").strip()
        wind_dir = str(item.get("windDir") or "未知风向").strip()
        wind_speed = str(item.get("windSpeed") or "?").strip()
        precip = str(item.get("precip") or "0").strip()
        pop = str(item.get("pop") or "").strip()
        cloud = str(item.get("cloud") or "").strip()

        extra_bits = [f"降水 {precip}mm"]
        if pop:
            extra_bits.append(f"降水概率 {pop}%")
        if cloud:
            extra_bits.append(f"云量 {cloud}%")

        lines.append(f"- {fx_time}｜{temp}°C｜{wind_dir} {wind_speed}km/h｜{'｜'.join(extra_bits)}")
    return lines


def _format_indices_lines(indices: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in indices:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        text = str(item.get("text") or "").strip()
        lines.append(f"- {name}：{text}" if text else f"- {name}")
    return lines


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


async def weather(
    location: str,
    adm: str = "",
    geo_range: str = "",
    tool_host: ToolHostBridge | None = None,
    tool_config: WeatherConfig | None = None,
) -> ToolOutcome:
    query = str(location or "").strip()
    config = tool_config or WeatherConfig()
    api_host = _norm_host(config.API_HOST)
    geo_host = _norm_host(config.GEO_HOST) or api_host
    api_key = str(config.API_KEY or "").strip()

    if tool_host is None:
        return _text_outcome("Weather Tool 缺少宿主桥接。", is_error=True, trace_summary="missing_host")
    if not query:
        return _text_outcome("请提供要查询的地点。", is_error=True, trace_summary="bad_args")
    if not api_host:
        return _text_outcome("天气服务未配置 API_HOST。", is_error=True, trace_summary="missing_api_host")
    if not api_key:
        return _text_outcome("天气服务未配置 API_KEY。", is_error=True, trace_summary="missing_api_key")

    await tool_host.log("info", "weather tool start", location=query, adm=adm, geo_range=geo_range)

    geo_params: dict[str, Any] = {"location": query, "lang": config.LANG, "number": 10}
    if str(adm or "").strip():
        geo_params["adm"] = adm.strip()
    resolved_geo_range = str(geo_range or config.GEO_RANGE or "").strip()
    if resolved_geo_range:
        geo_params["range"] = resolved_geo_range

    try:
        geo_payload: dict[str, Any] | None = None
        geo_candidates = [
            f"{geo_host}/geo/v2/city/lookup",
            f"{geo_host}/v2/city/lookup",
        ]
        if geo_host != "https://geoapi.qweather.com":
            geo_candidates.append("https://geoapi.qweather.com/v2/city/lookup")

        for geo_url in geo_candidates:
            try:
                geo_payload = await _request_json(
                    tool_host=tool_host,
                    url=geo_url,
                    params=geo_params,
                    api_key=api_key,
                    timeout=int(config.TIMEOUT),
                    allow_query_fallback=True,
                )
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    await tool_host.log("warning", "weather geo endpoint not found", url=geo_url)
                    continue
                if _is_no_such_location(exc):
                    await tool_host.log("info", "weather city lookup missed", location=query, url=geo_url)
                    geo_payload = {}
                    break
                raise

        geo_payload = geo_payload or {}
        location_id, location_name = _pick_location(query, geo_payload)
        if not location_id:
            if _RE_COORD.match(query) or query.isdigit():
                location_id = query
                location_name = query
            else:
                poi_payload = await _request_json(
                    tool_host=tool_host,
                    url=f"{geo_host}/geo/v2/poi/lookup",
                    params={"location": query, "lang": config.LANG, "number": 10, "type": "scenic"},
                    api_key=api_key,
                    timeout=int(config.TIMEOUT),
                    allow_query_fallback=True,
                )
                location_id, location_name = _pick_poi_location(query, poi_payload)
                if not location_id:
                    return _text_outcome(f"未找到地点：{query}", is_error=True, trace_summary="geo_not_found")

        weather_payload = await _request_json(
            tool_host=tool_host,
            url=f"{api_host}/v7/weather/24h",
            params={"location": location_id, "lang": config.LANG, "unit": "m"},
            api_key=api_key,
            timeout=int(config.TIMEOUT),
            allow_query_fallback=True,
        )
        if str(weather_payload.get("code") or "") != "200":
            return _text_outcome(
                f"天气服务返回异常代码：{weather_payload.get('code')}",
                is_error=True,
                trace_summary="weather_code_error",
            )

        indices_payload = await _request_json(
            tool_host=tool_host,
            url=f"{api_host}/v7/indices/1d",
            params={"location": location_id, "lang": config.LANG, "type": "1,3,5,8"},
            api_key=api_key,
            timeout=int(config.TIMEOUT),
            allow_query_fallback=True,
        )

        title = location_name or query
        hourly_lines = _format_hourly_lines(weather_payload.get("hourly") or [])
        indices_lines = []
        if str(indices_payload.get("code") or "") == "200":
            indices_lines = _format_indices_lines(indices_payload.get("daily") or [])

        lines = [f"天气查询：{title}"]
        if hourly_lines:
            lines.extend(["", "未来 24 小时预报：", *hourly_lines])
        if indices_lines:
            lines.extend(["", "今日指数：", *indices_lines])

        if len(lines) == 1:
            lines.append("未获取到有效天气结果。")

        text = "\n".join(lines).strip()
        await tool_host.log("info", "weather tool success", location=query, resolved_location=title, hourly=len(hourly_lines))
        return _text_outcome(text, is_error=False, trace_summary=f"weather:{title}")
    except httpx.HTTPStatusError as exc:
        await tool_host.log(
            "error",
            "weather tool http error",
            location=query,
            status_code=exc.response.status_code,
            url=str(exc.request.url),
        )
        return _text_outcome(
            f"天气服务请求失败（HTTP {exc.response.status_code}）。",
            is_error=True,
            trace_summary=f"http_{exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        await tool_host.log("error", "weather tool request error", location=query, error=str(exc))
        return _text_outcome("天气服务请求失败，请稍后再试。", is_error=True, trace_summary="request_error")
    except Exception as exc:
        await tool_host.log("error", "weather tool unexpected error", location=query, error=str(exc))
        return _text_outcome(f"天气查询失败：{exc}", is_error=True, trace_summary="unexpected_error")
