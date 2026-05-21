# 2026-05-18 secret toggle button mask fix

## 问题

- 适配器配置页面中，`is_secret` 字段在隐藏状态下会把尾部“显示/隐藏”按钮文字一并打点。
- Matrix、Telegram 只是前端上最容易看到的入口，实际影响面是统一配置表内全部 secret 配置项。

## 根因

- `frontend/src/components/common/ConfigTable.tsx`
- 旧实现把 `-webkit-text-security: disc` 直接挂在 `TextField` 的 `InputProps.style` 根节点上。
- MUI 的尾部按钮同处于该输入根节点内，因此按钮文本也被浏览器当作需要遮罩的文本一起渲染为圆点。

## 修复

- 保持现有 secret 字段交互不变，不新增分支逻辑。
- 仅将遮罩样式收缩到真实输入文本节点：`.MuiInputBase-input` 与 `textarea`。
- 结果是只有配置值被打点，尾部“显示/隐藏”按钮恢复正常可读。

## 影响评估

- 前端统一主干修复，覆盖全部 `is_secret` 配置项。
- 未改动后端、协议适配器、配置存储格式。
- 风险点仅在 MUI 输入样式选择器；通过前端构建验证。
