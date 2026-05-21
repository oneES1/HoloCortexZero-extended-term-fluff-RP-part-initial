# 2026-05-20 登录页神经网高级配色

## 目标

用户反馈当前神经网背景可以接受，但颜色偏死沉，需要更高级的背景配色方案，同时保持神经连接重点不被亮点抢走。

## 配色方案

采用低饱和多色暗调，而不是提高整体亮度：

- 深海黑青：作为主背景体积感。
- 极低饱和靛蓝：作为同簇神经连接主色。
- 墨绿青：作为跨簇连接与暗涌底色。
- 暗紫：用于少量连接和背景层次。
- 少量暖金：作为稀疏突触色，不做大面积发光。

## 修改内容

- 新增 `NEURAL_PALETTE`，集中管理背景色。
- 背景从单一黑蓝径向渐变改为：
  - `oilTeal -> midnight -> near black -> deepInk`
  - 叠加低透明度 `teal/violet/gold` 线性洗色。
- 暗涌宽线改为墨绿青与暗紫交替。
- 神经连接按聚簇关系分色：
  - 同簇：低饱和靛蓝为主。
  - 跨簇：墨绿青为主。
  - 少量突触：暖金/暗紫点缀。
- 节点仍保持低亮度，只做锚点，不重新变成亮点噪声。

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
- `vite build` 通过，转换模块数 `14084`，构建耗时约 `34.42s`。
