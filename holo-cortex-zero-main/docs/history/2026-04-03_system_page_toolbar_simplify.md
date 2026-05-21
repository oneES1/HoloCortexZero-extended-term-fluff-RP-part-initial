# System 页面工具栏与表格简化

## 本次调整
- 搜索框占位文案简化为 `搜索 / Search`。
- `保存更改`、`重置配置`、`重启` 统一放到搜索框同一排。
- `重置配置` 按钮改为红色。
- 删除 system 配置表头整行，不再显示蓝色横条与 `配置项 / 属性 / 类型 / 值`。
- 删除类型展示列，不再显示 `STR`、`LIST` 等标签。
- 删除模型组选项右侧的“XX模型组”跳转按钮，仅保留下拉选择。
- 将 system 页顶部独立的重启按钮收回到 `ConfigTable` 工具栏，避免重复操作入口。

## 影响文件
- `frontend/src/components/common/ConfigTable.tsx`
- `frontend/src/components/common/config-table/helpers.tsx`
- `frontend/src/pages/settings/system.tsx`
- `frontend/src/locales/zh-CN/common.json`
- `frontend/src/locales/en-US/common.json`
- `docs/2026-04-03_system_page_toolbar_simplify.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`

## 风险与回滚点
- 风险：本次仅改前端展示与交互布局，不改配置保存协议；主要风险是移动端拥挤，已通过按钮同排换行兜底。
- 回滚点：本次提交完成后可直接按提交哈希回退。
