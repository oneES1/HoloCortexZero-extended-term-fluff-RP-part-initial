# 2026-05-17 weather 景点 POI fallback 修复

## 修复内容

`weather` 工具保留原有城市查询主干，只在城市查询返回 QWeather `No Such Location` 且输入不是坐标/纯数字 ID 时，追加景点 POI fallback：

1. 先按旧逻辑调用 `/geo/v2/city/lookup`。
2. 城市搜索命中时，仍使用城市 LocationID 请求 `/v7/weather/24h`。
3. 城市搜索明确未命中时，调用 `/geo/v2/poi/lookup`，参数 `type=scenic`。
4. POI 命中后，不使用 POI id 查询天气，而是用 `lon,lat` 查询 `/v7/weather/24h`。

这个修复避免了 `雁栖湖` 这类景点名被城市搜索挡在 HTTP 400，同时不改变 `北京`、`怀柔`、`101010500`、`116.67000,40.39000` 等已有路径。

## 验证结果

真实容器、真实配置、真实 `tool_registry.execute(...)` 验证通过：

- `雁栖湖`: 成功，`trace_summary=weather:雁栖湖`，包含未来 24 小时预报。
- `怀柔`: 成功，保持城市查询路径。
- `北京`: 成功，保持城市查询路径。
- `101010500`: 成功，保持城市 ID 路径。
- `116.67000,40.39000`: 成功，保持坐标路径。

验证摘要：

- `all_ok=true`
- `is_error=false`: 5/5
- `has_weather_title=true`: 5/5
- `has_hourly=true`: 5/5

机器可读证据：

- `stage1_smoke/weather_real_tool_yanqihu_fix/summary.json`
- `stage1_smoke/weather_real_tool_post_recreate/summary.json`

## 命令

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker exec -i holo_cortex_zero bash -lc 'cd <CONTAINER_WORKSPACE_DIR>/holo-cortex-zero-main && env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy /app/.venv/bin/python scripts/validate_weather_real_tool.py --output-dir stage1_smoke/weather_real_tool_yanqihu_fix'
```

验证时未走 bot 消息注入，未写入 `context_window`、`context_message`、`tool_chain_trace`、memory/compression，也未触碰 `<ADVANCED_USER_ID>` 业务状态。

## 部署

普通后端代码改动已同步当前运行态：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

部署后状态：

- `holo_cortex_zero`: `healthy`
- `hcz_postgres`: 未重启，仍为原运行态
- `hcz_qdrant`: 未重启，仍为原运行态
- `hcz_napcat`: 未重启，仍为原运行态

部署后再次执行真实 `tool_registry.execute(...)` 验证，5/5 成功，`all_ok=true`。
