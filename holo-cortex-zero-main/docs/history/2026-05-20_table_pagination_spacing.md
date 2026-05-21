# 2026-05-20 通用分页按钮间距修正

## 背景

Tool Traces 底部翻页按钮过于紧凑。复核后确认分页入口统一使用 `TablePaginationStyled`，同一问题会影响用户管理、聊天窗口等复用该组件的页面。

## 变更

- 调整 `TablePaginationStyled` 的自定义翻页按钮：
  - 按钮间距从 `0.5` 增加到桌面 `1.25`、移动端 `1`。
  - 按钮最小宽度从 `0` 改为桌面 `64px`、移动端 `48px`。
  - 增加按钮横向 padding。
  - 移动端允许按钮换行，避免挤压。
- 调整分页 toolbar 整体留白与 gap。
- 强制分页 actions 区域 `margin-left: auto` 并右对齐，避免换行或空间变化时按钮跑到左侧。
- 自定义 `ActionsComponent` 透传 MUI 传入的 `className`，并把 `margin-left: auto` 落到真实 actions 根节点，避免父级选择器未命中。
- 将分页 toolbar 本身设为 `justify-content: flex-end`，并隐藏 MUI 内部 spacer，避免内部占位元素让按钮组回到左侧。

## 影响

- 影响所有使用 `TablePaginationStyled` 的页面。
- 不改变分页数据、页码逻辑与接口请求。

## 回滚点

- 还原 `frontend/src/components/common/TablePaginationStyled.tsx` 中本次样式调整。
