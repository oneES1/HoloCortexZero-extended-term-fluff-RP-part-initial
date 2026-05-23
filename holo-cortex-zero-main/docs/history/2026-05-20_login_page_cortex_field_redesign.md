# 2026-05-20 登录页动效表现重做

## 目标

用户反馈登录页动画表现差，要求审查并重做表现力。

## 审查结论

- 原登录页背景为随机点线网格，层次弱，和 HCZ 的品牌意象关联不足。
- 原页面主视觉、品牌文字、输入区依赖绝对定位，桌面可勉强成立，但移动端和窄屏容易失衡。
- 原输入和标题使用 viewport 参与字体缩放，不符合当前前端约束中“字体不随 viewport width 缩放”的要求。
- 原配色集中在黑/蓝/紫，表现偏单调。

## 修改

- 将 `NeuralMeshBackground` 重做为 `CortexFieldBackground`：
  - 使用确定性 canvas 场线，不再每次刷新随机重排。
  - 加入低亮度流线、核心环、扫描带、微粒信号，形成“中枢场”而不是零散点阵。
  - 支持 `prefers-reduced-motion`，降动效时保留静态画面。
- 将登录页布局从绝对定位改为响应式 grid：
  - 左侧 logo 作为第一视觉锚点。
  - 右侧品牌文本和登录输入形成连续阅读/操作动线。
- 调整输入线与 CTA 的焦点表现：
  - 用 cyan/blue/warm 三色信号线提升层次。
  - 删除 viewport 字体缩放和额外 letter spacing。
- 删除未使用字段与旧动画残留，避免僵尸代码。

## 验证

```bash
pnpm --dir frontend exec eslint src/pages/login/index.tsx
pnpm --dir frontend build
```

验证结果：

- `eslint src/pages/login/index.tsx` 通过。
- `vite build` 通过，转换模块数 `14084`，构建耗时约 `29.81s`。

## 影响范围

- 只修改 WebUI 登录页前端表现与登录页历史日志。
- 不修改后端、适配器、LLM 协议链路、Docker Compose。
- 不需要 Docker 重启；`frontend/dist` 通过现有 bind mount 同步运行态。
