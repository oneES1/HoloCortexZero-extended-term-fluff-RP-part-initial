# 2026-05-21 WebUI 亮色模式与专用 Logo 接入

## 背景

- 当前 WebUI 已有暗色主题主干，但亮色模式入口还不完整。
- 顶部导航与登录页此前都直接绑定暗色 logo，切换到亮色模式后视觉不一致。

## 本次最小修改

- `frontend/src/theme/glass.ts`
  - 保留旧常量名，改为通过 CSS 变量承接，避免把主题主干拆成两套并行实现。
  - 新增 `getGlassTokens(mode)`，供主题 provider 按 `light / dark` 输出实际值。
- `frontend/src/index.css`
  - 为 `dark` 与 `light` 两种模式写入全局 CSS 变量默认值与覆盖值。
  - 让旧组件继续使用原常量名时也能自动跟随模式变化。
- `frontend/src/theme/ThemeProvider.tsx`
  - 按当前 `mode` 写入 `data-theme`，让全局变量切换生效。
  - MUI 主题按 `mode` 生成对应配色与面板样式。
- `frontend/src/layouts/MainLayoutNew.tsx`
  - 顶栏 logo 改为按 `mode` 切换 `logo_darkmode.png` / `logo_lightmode.png`。
- `frontend/src/pages/login/index.tsx`
  - 登录页 logo 同步按 `mode` 切换。
- `frontend/src/assets/logo_lightmode.png`
  - 新增专用亮色 logo 资源。

## 影响范围

- 影响 WebUI 的主题切换、顶部导航、登录页与依赖 `glass.ts` 的旧组件样式。
- 不改路由，不改接口，不改登录流程，不改后端协议。

## 风险

- 风险中等：主题变量链路较长，但通过保留旧常量名与 CSS 变量承接，尽量避免拆分主干。
- 若某个组件直接写死了深色数值且不走 `glass.ts`，仍可能需要后续补齐。

## 复盘补记

- 首次接入后，前端出现黑屏，现场验证到 MUI `createTheme` 会对 `palette.secondary.main` 做颜色运算；当它拿到 `var(--...)` 时会直接抛错。
- 已将 `palette.secondary.main` 改回按当前 `mode` 输出的真实 hex 值，避免主题初始化阶段崩溃。

## 浅色模式补修

- 修复登录页仍使用暗色背景的问题：根容器、Canvas 背景、神经网络底图、输入框、CTA、标题与副标题均按 `mode` 切换颜色。
- 修复浅色模式列表 hover 过深的问题：适配器侧栏、配置表、仪表盘追踪列表、日志行统一改用 MUI `action.hover / action.selected`。
- 修复浅色模式残留白字：通知组件与统计卡数值改用当前主题的 `text.primary`，日志行正文改用主题文字色。
- 验证：`pnpm --dir frontend build` 成功，Vite 输出 `✓ built in 30.40s`。

## 浅色登录页视觉补调

- 浅色 logo 本体为黑色时，移除暗色模式的蓝绿发光，改为轻量投影并将不透明度降至 `0.88`，降低纯黑压迫感。
- 浅色主标题从 `rgba(15,23,42,0.62)` 加深到 `0.88`，副标题从 `0.48` 加深到 `0.66`，与黑色 logo 视觉重量更一致。
- 浅色输入文字改为 `#0f172a`，placeholder 从 `0.42` 加深到 `0.56`，未聚焦输入线从 `0.22` 加深到 `0.34`。
- 验证：`pnpm --dir frontend build` 成功，Vite 输出 `✓ built in 29.72s`。

## 默认暗色模式补记

- 主题 store 的代码默认值已是 `dark`，但旧浏览器缓存 key `color-mode` 会让曾切到浅色的客户端继续保持浅色。
- 将主题持久化 key 升级为 `color-mode-v2`，让没有新缓存的客户端重新落到暗色默认值；之后用户手动切换仍会持久化。
- 验证：`pnpm --dir frontend build` 成功，Vite 输出 `✓ built in 29.93s`。

## 浅色页面残留黑底补修

- 修复 dashboard 实时图表浮标仍为黑色：tooltip 改用当前主题 `background.paper / divider`，坐标轴与网格按主题文字色和浅色分隔线输出。
- 修复 tool traces 页面浅色下仍有黑色卡片：列表卡片、时间线卡片、代码/文本块、顶部统计分隔线改用主题 surface；代码高亮浅色模式切到 `oneLight`。
- 修复 logs 页面配色不一致：筛选栏、日志列表容器、表头、日志详情弹窗正文块改用主题 surface、divider 与文字色。
- 修复 model group 页面浅色下卡片 hover、按钮、分区 hover、模型卡片边框仍沿用暗色值的问题。
- 验证：`pnpm --dir frontend build` 成功，Vite 输出 `✓ built in 37.91s`。

## 回滚点

- 回滚 `frontend/src/theme/glass.ts`、`frontend/src/index.css`、`frontend/src/theme/ThemeProvider.tsx`、`frontend/src/layouts/MainLayoutNew.tsx`、`frontend/src/pages/login/index.tsx` 和 `frontend/src/assets/logo_lightmode.png` 即可。
