# 2026-04-03 frontend state single-source cleanup

## 背景

本次清理针对前端 `zustand` store 中已经出现的多真相源与遗留彩蛋问题，目标是在**不扩散功能面**的前提下收束主干、删除死分支、降低状态歧义。

## 发现

### 1. auth
- `frontend/src/stores/auth.ts` 之前使用 `persist` 默认落到 `localStorage`
- `axios` / `stream` 又直接从 store 取 token，因此该 store 确实属于运行主干
- 风险点在于 token 长期留在 `localStorage`，会放大 XSS 后果

### 2. locale
- `frontend/src/stores/locale.ts` 会持久化 `currentLocale`
- `frontend/src/config/i18n.ts` 同时启用了 `i18next-browser-languagedetector` 的 `localStorage` 缓存
- 结果是语言状态有两份缓存，store 与 i18next 都可能成为“真相源”

### 3. theme
- `frontend/src/stores/theme.ts` 保留了 `presetId` / 自定义颜色字段 / 自定义 setter
- `frontend/src/theme/palette.ts` 又绕过 store 直接读取 `localStorage('color-mode')`
- `frontend/src/theme/ThemeProvider.tsx` 还通过 `hcz-theme-change` 自定义事件强制刷新
- 三条链路并存，主题主干不干净

### 4. dev 彩蛋
- `frontend/src/stores/devMode.ts` 只服务 `MainLayout`
- `frontend/src/hooks/useSecretCode.ts` 只用于 Logo 点击序列彩蛋
- 当前效果仅为切换一个 `DEV` 标识，无权限、无功能增益，属于低价值遗留

## 本次修改

### auth
- 将 `auth` store 的持久化介质从 `localStorage` 收紧为 `sessionStorage`
- 保留原有 store API 与调用方式，不改登录/退出/请求拦截主干

### locale
- 移除 `i18next-browser-languagedetector`
- 取消 i18next 自己的 `localStorage` 语言缓存
- 保留 `locale` store 作为唯一语言真相源
- 在 store rehydrate 后主动同步 `i18next.changeLanguage`

### theme
- 删除主题预设与自定义颜色的死字段、死 setter、死导出
- 删除 `palette.ts` 中绕过 store 的 `localStorage('color-mode')` 初始化分支
- 删除 `ThemeProvider.tsx` 中 `hcz-theme-change` 自定义事件监听
- 保留 `mode` 与 `performanceMode` 作为当前唯一主题状态

### dev 彩蛋
- 删除 `frontend/src/stores/devMode.ts`
- 删除 `frontend/src/hooks/useSecretCode.ts`
- 删除 `MainLayout` 中的彩蛋触发与 `DEV` 标识
- 删除对应的中英文文案残留

## 影响面

- 登录态仍可跨刷新保留，但不再跨浏览器会话长期留存
- 语言切换改为由 store 单点驱动，避免与 i18next 自缓存打架
- 主题系统删除未实际使用的预设/自定义分支后，主干只剩亮暗模式与性能模式
- 顶部 Logo 不再响应隐藏点击序列

## 验证

执行：

```bash
cd /path/to/source-root && pnpm --dir frontend build
```

结果：构建通过。

## 回滚点

- `98c6f13` `fix(frontend): move auth store to session storage`
- `6a37969` `refactor(frontend): make locale store the single source`
- `4442ec4` `refactor(frontend): remove theme dead branches and dev easter egg`
- `a9319a7` `refactor(frontend): remove main layout dev mode hooks`
