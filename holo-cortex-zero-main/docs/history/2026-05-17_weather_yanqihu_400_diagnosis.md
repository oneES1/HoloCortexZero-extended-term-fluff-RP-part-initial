# 2026-05-17 weather 雁栖湖 HTTP 400 诊断

## 结论

`weather` 工具对 `location="雁栖湖"` 报 `天气服务请求失败（HTTP 400）` 的直接原因是：当前工具只走城市搜索 `/geo/v2/city/lookup`，但 `雁栖湖` 是景点 POI，不是城市 LocationID 查询能解析的地点。

真实配置与真实请求验证显示：

- `/geo/v2/city/lookup?location=雁栖湖&range=cn` 返回 HTTP 400，错误为 `No Such Location`。
- `/geo/v2/poi/lookup?location=雁栖湖&type=scenic` 返回 HTTP 200，命中 1 个 POI：`雁栖湖`，`id=10101050008A`，`lon=116.67000`，`lat=40.39000`。
- `/v7/weather/24h?location=10101050008A` 返回 HTTP 400，错误为 `invalidParams=["location"]`。
- `/v7/weather/24h?location=116.67000,40.39000` 返回 HTTP 200，`code=200`，`hourly_count=24`。
- `/v7/weather/24h?location=101010500` 返回 HTTP 200，`code=200`，`hourly_count=24`。

因此最小修复方向不是把 POI id 当成天气 LocationID，而是在城市搜索未命中且查询不是坐标/纯 ID 时，增加 POI scenic fallback，并将命中的 POI 转成 `lon,lat` 再请求天气。

## 复现环境

- 容器：`holo_cortex_zero`
- 配置文件：`<CONTAINER_DATA_DIR>/configs/tools/weather.yaml`
- `API_HOST`: `https://k373jqk554.re.qweatherapi.com`
- `GEO_HOST`: `https://k373jqk554.re.qweatherapi.com`
- `API_KEY`: 已配置，长度 32，诊断记录未写入密钥
- `GEO_RANGE`: `cn`
- `LANG`: `zh`
- `TIMEOUT`: `10`

## 证据文件

机器可读证据见：

- `stage1_smoke/weather_yanqihu_400_diagnosis/summary.json`

## 约束

本轮仅诊断与记录，没有修改 `weather` 业务代码，没有重建容器，没有触发 bot 注入、上下文窗口、`context_message`、tool trace、memory/compression 写入，也没有触碰 `<ADVANCED_USER_ID>` 业务状态。
