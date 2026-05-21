# 2026-05-21 登录页密码框黄底修复

## 问题

用户反馈密码填写完整后，密码输入框出现突兀的土黄色背景。

## 根因判断

登录页输入框本身是透明背景，但浏览器或密码管理器会对 `password` 输入框应用 autofill 默认背景色。由于登录页是暗色透明输入风格，该默认黄底会非常突兀。另有输入下划线/CTA 使用亮金 `#f5b85a`，在当前暖色背景下也容易强化“土黄”观感。

## 修改内容

- 为登录页输入框增加 autofill 覆盖：
  - `&:-webkit-autofill`
  - `&:-webkit-autofill:hover`
  - `&:-webkit-autofill:focus`
  - `&:autofill`
- 强制 autofill 文本色、光标色保持浅色。
- 使用超长 `background-color` transition 避免浏览器黄底闪现。
- 使用极低透明度 inset shadow 压掉 WebKit autofill 背景。
- 将输入/CTA 暖金线条从 `#f5b85a` 降为 `#b98b52`，避免高饱和黄橙突兀。

## 未修改

- 不修改神经网背景结构。
- 不修改登录页字体、字距、输入节奏。
- 不修改 logo、品牌文案、登录框位置。
- 不修改登录逻辑。

## 验证

```bash
pnpm --dir frontend exec eslint src/pages/login/index.tsx
pnpm --dir frontend build
```

验证结果：

- `eslint src/pages/login/index.tsx` 通过。
- `vite build` 通过，转换模块数 `14084`，构建耗时约 `31.54s`。
