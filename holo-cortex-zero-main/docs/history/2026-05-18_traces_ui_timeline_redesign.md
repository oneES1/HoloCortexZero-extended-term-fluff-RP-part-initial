# 2026-05-18 Traces UI 完全重做 —— 时间线布局与零边框设计

## 背景

Traces 详情 UI 被层层 `Paper variant="outlined"` 与 `Chip variant="outlined"` 包裹，形成"一圈框起来文字"的廉价视觉效果。用户明确要求完全删除旧设计、重新设计、追求高级感与版面设计感。

## 修改

- `frontend/src/pages/tool-traces/index.tsx`（完全重写，64% 变更）
  - `TraceEventCard` → `TimelineEventCard`：
    - 左侧时间线列：2px 竖线贯穿 + 8px 彩色圆点节点（LLM 蓝 / Assistant 绿 / Tool 橙 / Error 红）。
    - 内容区彻底去边框：背景 `rgba(255,255,255,0.015)`，圆角 12px，无 `border` 或 `outline`。
    - Kind badge 采用背景色块模式（`rgba(color,0.12)` + 同色文字），消灭 outlined Chip。
    - LLM metadata 改为纯文本横排（`finish_reason · 2 tool calls · tokens · cache · iterations`），字号 0.7rem，颜色 `text.disabled`。
    - reasoning / assistant / arguments / result 内容区统一使用 `#111113` 深色嵌块 + 8px 圆角，SyntaxHighlighter 背景透明直接嵌入。
    - Error 事件内容区背景 `rgba(255,69,58,0.04)`，文字红色。
  - `TraceDetailContent` → `TraceDetailView`：
    - 顶部 Header：trigger message 前 80 字为大标题（1.1rem/600），下方副标题显示时间/总耗时/tokens。
    - Metadata bar 一行横排纯文本（Context / Dialog / Permission / Model），消灭 Chip 堆叠。
    - Trigger 与 Summary 两个 Section：上方 uppercase label（0.65rem，tracking-wide），下方 `#111113` 内容块。
    - Copy 按钮改为 hover 时右上角浮现 `ContentCopy` icon button，不再常驻。
    - Trace Events Section：Label + 复制全量 JSON icon + TimelineEventCard 列表。
  - `ToolTracesPage` 列表页从 Table + Collapse 改为**卡片流**：
    - 顶部 stats bar：Total / Success / Failed / Rate 四列，无上边框底线 `rgba(255,255,255,0.06)` 分隔。
    - 每行卡片 `bgcolor: #0d0d0f`，圆角 12px，hover 微亮。
    - 卡片内：6px 状态圆点（无 glow）+ 时间戳 + 单行文本 + model · duration · tool count。
    - 右侧箭头图标指示展开/收起。
    - 底部分页保留 `TablePaginationStyled`。
  - 向后兼容：导出 `TraceDetailView as TraceDetailContent`，Dashboard 无需改导入名。

- `frontend/src/pages/dashboard/index.tsx`
  - `ChainListItem` 去边框化：移除 `border: 1px solid`，选中态改为左侧 3px `primary.main` accent bar + `rgba(255,255,255,0.04)` 背景，hover 为 `rgba(255,255,255,0.03)`。
  - 状态圆点从 8px 缩至 6px，移除 `boxShadow` glow。
  - Overview Option 同步应用相同去边框 + 左侧 accent bar 设计。
  - 右侧面板移除对 `.MuiPaper-root`、`.MuiAlert-root`、`.MuiChip-root` 的全局覆盖样式（旧设计 workaround 已失效）。

- `holo_cortex_zero/routers/tool_traces.py`
  - `/stats` 接口从统计全部历史改为仅统计**最近 1000 条**。
  - 新增可选 `recent` 查询参数（默认 1000），避免大数据量下 success_rate 被早期历史稀释。

## 验证

- `cd /path/to/source-root && pnpm --dir frontend build`
  - 结果：✓ built in 38.62s，无编译错误，无类型错误。

## 风险与回滚点

- 风险：列表页从 Table 改为卡片流后，若 trace 数量极大（单页 100+）滚动性能需观察；当前每卡片为轻量 MUI Box/Paper，无复杂嵌套。
- 回滚点：本次 `refactor` 提交 `2fd7757`。
