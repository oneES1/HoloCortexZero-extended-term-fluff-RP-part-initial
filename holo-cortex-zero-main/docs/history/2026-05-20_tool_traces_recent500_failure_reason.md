# 2026-05-20 Tool Traces 近 500 成功率与成功轮数

## 背景

Tool Traces 顶部统计原先显示 `Total / Success / Failed / Rate`，其中 `total` 来自后端默认最近 1000 条窗口，固定显示 1000 容易造成误读。用户确认目标口径为：只展示最近 500 条的成功率与成功轮数，同时支持中英文。

## 变更

- `/tool-traces/stats` 默认统计窗口从最近 1000 条改为最近 500 条。
- 前端 `toolTracesApi.getStats()` 默认传 `recent=500`。
- Tool Traces 顶部统计栏删除 `Total / Failed`，只保留“近500条成功率”与“近500次成功轮数”。
- 成功率与成功轮数均来自 `/tool-traces/stats?recent=500`，设置 10 秒刷新。
- `zh-CN` 与 `en-US` 补齐新文案。

## 当前数据证据

只读查询当前运行库最近 500 条：

- `total=500`
- `success=500`
- `failed=0`
- `success_rate=100.00`
- 时间范围：`2026-05-09 01:12:49.820589+08` 到 `2026-05-20 08:34:19.810488+08`

## 影响

- 独立 Tool Traces 页面顶部统计变窄，只显示核心成功率与成功轮数。
- 后端 `/tool-traces/stats` 仍保留 `recent` 查询参数，可显式覆盖窗口。
- 列表分页数据不变。

## 回滚点

- 还原 `holo_cortex_zero/routers/tool_traces.py` 中 `recent` 默认值。
- 还原 `frontend/src/pages/tool-traces/index.tsx` 顶部 Stats bar。
- 还原 `frontend/src/services/api/tool-traces.ts` 的 `getStats()` 参数。
- 删除本次新增 locale key。
