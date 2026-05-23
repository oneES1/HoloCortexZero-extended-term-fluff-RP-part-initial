# Prompt 管理页滚动与高度自适应修整

## 本次调整
- 固定 `MainLayoutNew` 主内容区高度为视口减去顶部栏，避免 Prompt 页把内容高度继续往下撑开。
- `ManagePage` 改为继承父容器高度并隐藏外层滚动，确保管理类页面优先走内部滚动。
- Prompt 管理页根容器保持满高，顶部工具栏固定不参与滚动。
- 左右分栏都改为占满剩余高度，并各自独立滚动，不再出现整页滚动。
- 小屏时改成上下两块自适应比例布局，上半列表、下半编辑器，仍然由分栏内部滚动。

## 影响文件
- `frontend/src/layouts/MainLayoutNew.tsx`
- `frontend/src/pages/manage/index.tsx`
- `frontend/src/pages/prompt-management/index.tsx`
- `docs/2026-04-03_prompt_management_scroll_fit.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`

## 风险与回滚点
- 风险：本次会影响 `Manage` 区域共用高度链路，但只调整容器高度与 overflow，不改业务逻辑。
- 回滚点：本次提交完成后可直接按提交哈希回退。
