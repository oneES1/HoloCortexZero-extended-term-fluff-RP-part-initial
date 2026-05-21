# 2026-05-18 模型组前端运行时崩溃修复

## 背景

- `frontend/src/pages/settings/model_group.tsx` 在模型组配置卡片里直接调用了 `alpha(...)`，但文件顶部没有导入 `alpha`。
- 该页面还直接使用了 `ChatBubbleOutlineIcon`、`ScatterPlotIcon`、`ImageOutlinedIcon`，但对应图标也没有导入。
- 两个 `Dialog` 仍沿用了与当前 MUI 类型定义不兼容的 `slotProps.paper` 写法，`tsc` 会在这里报错。

## 修改

- 补入 `alpha` 的正确导入：`@mui/material/styles`。
- 补入三个缺失图标的导入：`ChatBubbleOutline`、`ScatterPlot`、`ImageOutlined`。
- 将两个 `Dialog` 的 `slotProps.paper` 改为当前项目已使用的 `PaperProps`，保留同样的样式主干。
- 删除 `Divider`、`Grid`、`isMobile`、`modelTypes` 等已确认无用项。
- 不扩散到其他页面，不改业务逻辑，不新增分支。

## 验证

- `cd /home/ubuntu/hcz-deploy/holo-cortex-zero-main/frontend && pnpm exec eslint src/pages/settings/model_group.tsx`
  - 结果：通过。
- `cd /home/ubuntu/hcz-deploy/holo-cortex-zero-main/frontend && pnpm exec tsc -p tsconfig.app.json --noEmit`
  - 结果：`model_group.tsx` 相关报错已清零；仓库里仍存在其他无关 TS 报错。
- `cd /home/ubuntu/hcz-deploy/holo-cortex-zero-main/frontend && pnpm build`
  - 结果：通过，`✓ built in 37.37s`。
- `cd /home/ubuntu/hcz-deploy && printf 'HCZ425170\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero`
  - 结果：`holo_cortex_zero` 已重建并启动。

## 风险与回滚点

- 风险：仅为前端页面局部修复，风险集中在 `model_group` 页的样式色块渲染。
- 回滚点：撤销 `alpha` 导入、未使用项删除，以及本次 `docs/history` 记录即可。
