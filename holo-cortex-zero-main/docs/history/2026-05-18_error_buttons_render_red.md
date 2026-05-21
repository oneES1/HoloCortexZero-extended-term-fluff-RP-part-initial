# 2026-05-18 error buttons render red

## 问题

`Reset/Danger Operations` 相关按钮在页面上仍然显示为蓝色。

## 定位

前端主题里 `MuiButton.contained` 和 `MuiButton.outlined` 的全局样式把按钮外观统一成了蓝色玻璃风格，导致 `color="error"` 只保留了语义，不会在视觉上变红。

## 修改

在 `frontend/src/theme/ThemeProvider.tsx` 中补了 `MuiButton-containedError` 和 `MuiButton-outlinedError` 的主题覆盖，让所有 `error` 按钮在保持现有按钮结构的前提下显示红色。

## 验证

- 目标按钮：`MainLayoutNew` 里的危险操作弹窗按钮
- 影响范围：所有 `MuiButton color="error"` 的 contained / outlined 变体
- 回滚点：移除 `MuiButton-containedError` / `MuiButton-outlinedError` 覆盖即可恢复原样
