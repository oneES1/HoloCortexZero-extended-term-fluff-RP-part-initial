# Logs 页面简化与底部粘连滚动

## 本次调整
- 删除 `高级模式`、`来源`、`自动滚动`、`行数`、`下载` 相关 UI 与逻辑。
- 顶部只保留 `搜索框 + 日志级别`，并将日志级别放到搜索框右侧。
- 去掉日志列表顶部蓝色表头，不再显示 `时间 / 级别 / 消息 / 来源` 横条。
- 自动滚动改为“仅在列表位于底部时自动跟随”；若用户手动上滑查看历史且不在底部，则停止自动滚动。
- 日志行布局改为给 `时间戳` 更宽空间、保留 `级别`、压缩 `消息` 展示宽度，并移除列表中的 `来源` 列。

## 影响文件
- `frontend/src/pages/logs/index.tsx`
- `frontend/src/pages/logs/components/LogsTableRow.tsx`
- `docs/2026-04-03_logs_simplify_and_sticky_scroll.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`

## 风险与回滚点
- 风险：本次简化后日志页不再支持来源筛选与下载入口；如后续仍需下载，可保留到隐藏入口再议。
- 回滚点：本次提交完成后可直接按提交哈希回退。
