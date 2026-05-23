# 前端仪表盘微调记录

## 本次调整
- 修复新顶栏左上角 Logo 贴图，改为使用前端打包资源而非直接写死 `/logo.png`。
- 删除仪表盘中重复的信息块：`概览`、`Tool链运行状态`、`Agent运行成功率`、`分布统计`。
- 保留原有更完整的实时流图，并将标题从“实时数据”改为“运行概览”。
- 将粒度选择文案从“数据粒度”改为“时间刻度”。
- 删除顶部统计卡中的 `活跃频道`、`独立用户`、`Tool链成功率`，仅保留核心计数。

## 影响文件
- `frontend/src/layouts/MainLayoutNew.tsx`
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/locales/zh-CN/dashboard.json`
- `frontend/src/locales/en-US/dashboard.json`
- 删除：`frontend/src/pages/dashboard/components/TrendsChart.tsx`
- 删除：`frontend/src/pages/dashboard/components/DistributionsCard.tsx`

## 验证
- `cd /path/to/source-root/frontend && pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `9ed32a1` `fix(frontend): wire new ui to real pages`
