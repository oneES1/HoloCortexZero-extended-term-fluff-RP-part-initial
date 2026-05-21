# 2026-05-20 登录页神经网暗涌动效

## 目标

用户明确要求登录页动效为“网状、暗涌、神经网络、交织”，而不是扫描线、环形脉冲或普通粒子场。

## 修改范围

- 只修改登录页 canvas 背景动效层 `CortexFieldBackground`。
- 不修改 logo、品牌文案、登录框的位置。
- 不修改登录鉴权逻辑、路由、后端、Docker Compose。

## 修改内容

- 删除扫描带、环形脉冲、横向流线式表现。
- 改为确定性的神经网络场：
  - `118` 个神经节点。
  - 每个节点最多 `4` 条 synapse 曲线连接。
  - `5` 个聚簇区域，形成交织网络结构。
  - 节点做低速漂移，连接线使用二次曲线弯曲，制造“交织”感。
  - 叠加低透明度宽曲线作为背景暗涌，而不是明亮扫描线。
  - 连接线上有低亮度信号流动，但整体保持暗色。
- 保留 `prefers-reduced-motion` 支持，降动效时冻结流动但保留神经网画面。

## 位置复核

登录页主体坐标保持：

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
- `vite build` 通过，转换模块数 `14084`，构建耗时约 `34.32s`。
