# Dashboard Tool 调用统计口径修正

## 背景

用户反馈前端 `Tool链运行` 统计量与 `成功运行` 重叠，不能表达真实工具调用次数；同时要求运行概览图去掉 `消息数` 曲线。

## 本次最小修改

- 后端 `Dashboard` 保留既有 API 字段名 `total_tool_chain_runs` / `recent_tool_chain_runs`，但统计口径改为从 `DBToolChainTrace.trace_json.diagnostics.tool_calls_executed_total` 求和。
- 对旧轨迹或缺少 diagnostics 的记录，回退按 `trace_json.events` 中 `kind == "tool"` 的事件数统计，避免历史数据直接归零。
- `成功运行` / `失败运行` 继续按 `DBToolChainTrace` 运行记录统计，不再用 `Tool调用数 - 成功运行数` 推导失败数，避免混合口径。
- 前端运行概览图删除 `消息数` 曲线，仅保留 `Tool调用数`、`成功运行`、`失败运行`。
- 前端显示文案从 `Tool链运行` 调整为 `Tool调用数` / `Tool Calls`，避免继续误解为运行记录数。

## 影响范围

- 影响 `/dashboard/overview`、`/dashboard/trends`、`/dashboard/stats/stream` 的 tool 统计口径。
- 不修改 tool 链执行、tool trace 落库、消息总数卡片和聊天消息统计逻辑。
- 不做历史库重写；历史 trace 通过读取 `trace_json` 动态聚合。

## 验证记录

- `python3 -m py_compile holo_cortex_zero/routers/dashboard.py`
- `python3 -m json.tool frontend/src/locales/zh-CN/dashboard.json`
- `python3 -m json.tool frontend/src/locales/en-US/dashboard.json`
- `git diff --check`
- `pnpm --dir frontend build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`
- `docker inspect` 确认 `holo_cortex_zero` health 为 `healthy`

构建提示存在既有 Browserslist 数据过期和 chunk 体积提示，本次未联网更新依赖，也未调整打包分片。

## 回滚点

回滚本次提交即可恢复旧口径；无需数据库回滚。
