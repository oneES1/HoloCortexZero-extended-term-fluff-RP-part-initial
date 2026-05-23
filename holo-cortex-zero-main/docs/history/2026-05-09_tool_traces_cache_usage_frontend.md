# 2026-05-09 Tool Traces 缓存命中显示

## 背景

主模型组已在 `ToolChainExecutor` 的 `trace_json.events[].usage` 中记录 `cached_tokens`。为了在前端直接判断 deep/deek 慢因，需要把该字段显示到 Tool Traces 详情页。

## 变更

- `frontend/src/services/api/tool-traces.ts`
  - `ToolTraceUsage` 增加可选字段 `cached_tokens`。
- `frontend/src/pages/tool-traces/index.tsx`
  - 新增 `formatCacheRatio()`。
  - 在 LLM 事件卡片的 token chip 后显示缓存 chip：`缓存 <cached_tokens> · <cache_ratio>`。
  - `cached_tokens > 0` 时 chip 使用 success 色，便于扫视命中轮次。
- `frontend/src/locales/zh-CN/tool-traces.json`
  - 增加 `detail.trace.cacheUsage`。
- `frontend/src/locales/en-US/tool-traces.json`
  - 增加 `detail.trace.cacheUsage`。

## 影响范围

- 只影响 Tool Traces 详情页展示。
- 不改变后端 API、trace 存储、LLM 请求、缓存策略。
- 旧 trace 没有 `cached_tokens` 时不显示缓存 chip。

## 验证方式

1. 前端构建：

```bash
cd /path/to/source-root
pnpm --dir frontend build
```

2. 运行态同步后，在前端打开 `/monitor/traces`，查看新产生的 LLM 事件卡片：

- 命中缓存：显示 `缓存 14443 · 99.9%` 类似 chip。
- 未命中缓存：若新 trace 有字段则显示 `缓存 0 · 0.0%`。
- 旧 trace：不显示缓存 chip。

## 风险与回滚

- 风险低：纯前端展示字段，字段缺失时自动隐藏。
- 回滚点：撤回本次前端四个文件改动，并删除本文档。
