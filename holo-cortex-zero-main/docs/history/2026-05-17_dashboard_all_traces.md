# Dashboard All Traces

## 背景

Dashboard 左侧链路列表只显示高级 context 记录。复核链路后确认 `/tool-traces/logs` 后端接口默认使用 `DBToolChainTrace.all()`，没有按 `permission_level` 过滤；限制来自前端 Dashboard 本地筛选。

证据：

- `frontend/src/pages/dashboard/index.tsx` 原逻辑存在 `trace.permission_level === 'advanced'`。
- `holo_cortex_zero/routers/tool_traces.py` 的 `get_tool_trace_logs()` 默认查询 `DBToolChainTrace.all()`，仅在传入 `chat_key` 或 `success` 时追加过滤。

## 变更

- Dashboard 最近链路列表改为直接展示 `/tool-traces/logs?page=1&page_size=20` 返回的全部 trace。
- 移除 Dashboard 内部的高级 context 命名残留。
- 空态文案 key 从 `noAdvancedTrace` 改为 `noTrace`。

## 影响

- Dashboard 左侧最多展示最近 20 条全部 trace，不再局限于高级 context。
- Tool Traces 独立页面、后端 trace 接口、统计流均未修改。
- 回滚点：还原 `frontend/src/pages/dashboard/index.tsx` 中的 `permission_level === 'advanced'` 过滤及对应文案 key。

## 验证

- `rg -n "noAdvancedTrace|dashboard-latest-advanced-trace|permission_level === 'advanced'|advancedTraces" frontend/src -S`
- `pnpm --dir frontend exec tsc --noEmit`
