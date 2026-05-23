# 2026-05-21 登录页字体重心恢复

## 问题

用户指出登录页字体被改动后视觉重心坍塌。复查确认此前将标题、slogan、输入框、CTA 的 `letterSpacing` 收为 `0`，破坏了原登录页依赖大字距建立的视觉重心。

## 恢复内容

- 品牌标题字距恢复为 `0.28em`。
- slogan 字距恢复为 `0.08em`。
- 输入框字距恢复为 `0.06em`。
- CTA 字距恢复为 `0.18em`。
- 输入框宽度恢复为 `clamp(260px, 16vw, 380px)`。
- 输入框垂直节奏恢复为 `marginBottom: 3vh` 与 `py: 1.6vh`。
- 品牌标题与 slogan 的颜色和 text-shadow 恢复到原视觉重心参数。

## 未修改

- 不修改背景神经网动效结构。
- 不修改高级配色方案。
- 不修改 logo、品牌文案、登录框位置。
- 不修改登录鉴权逻辑。

## 位置复核

- logo：`left: 7vw; top: 10vh`
- 品牌文案：`left: 42vw; top: 40vh`
- 登录框：`right: 12vw; bottom: 5vh`

## 验证

```bash
pnpm --dir frontend exec eslint src/pages/login/index.tsx
pnpm --dir frontend build
```

验证结果：

- `eslint src/pages/login/index.tsx` 通过。
- `vite build` 通过，转换模块数 `14084`，构建耗时约 `37.24s`。
