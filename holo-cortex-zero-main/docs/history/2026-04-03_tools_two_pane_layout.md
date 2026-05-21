# Tools 管理页双栏与信息裁剪

## 本次调整
- 删除页面顶部 `工具管理` 标题与其下说明文案。
- 页面改为类似聊天窗口的双栏布局，外层不滚动，左右分栏各自独立滚动。
- 左侧仅展示 Tool 中文名、调用名称（`tool_id`）与说明文字，不再显示范围、分类、状态 chips，也不再显示范围选择器。
- 右侧上半部分直接展示 Tool 配置项，右上角保留 `保存更改 / 重置配置`，其中 `重置配置` 改为红色。
- 右侧下半部分仅展示调用参数 `parameters_schema`，不再显示其它说明与状态信息。

## 影响文件
- `frontend/src/pages/tools/management.tsx`
- `frontend/src/components/common/ConfigTable.tsx`
- `frontend/src/components/common/config-table/types.ts`
- `docs/2026-04-03_tools_two_pane_layout.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`

## 风险与回滚点
- 风险：本次将 Tool 范围切换入口从页面中移除，降低误操作但也不再支持在该页直接改 scope；未改后端接口。
- 回滚点：本次提交完成后可直接按提交哈希回退。
