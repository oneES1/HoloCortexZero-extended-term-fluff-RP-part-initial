# 危险操作入口收口到头像菜单

## 本次调整
- 将 `system` 页工具栏中的 `重置配置` 与 `重启` 按钮隐藏，不再显眼展示。
- Prompt 管理页顶部移除 `重置配置` 按钮，仅保留 `保存更改`。
- 在头像菜单中、`Sign Out` 上方新增 `重置` 入口。
- 点击 `重置` 后弹出居中危险操作菜单，仅显示红色的 `重置配置` 与 `重启` 按钮。
- 危险菜单中的 `重置配置` 统一执行 `system` 配置 reload，`重启` 统一发送系统重启请求。

## 影响文件
- `frontend/src/layouts/MainLayoutNew.tsx`
- `frontend/src/components/common/ConfigTable.tsx`
- `frontend/src/pages/prompt-management/index.tsx`
- `docs/2026-04-03_danger_actions_hidden_menu.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`

## 风险与回滚点
- 风险：危险操作被统一到头像菜单后，路径更深，但可见性更低；本次不改变后端接口与真实行为。
- 回滚点：本次提交完成后可直接按提交哈希回退。
