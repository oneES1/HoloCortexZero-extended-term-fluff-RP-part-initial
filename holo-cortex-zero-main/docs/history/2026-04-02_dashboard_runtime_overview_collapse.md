# Dashboard 运行概览折叠化与时间刻度收口

## 本次调整
- 删除 Dashboard 顶部的 `今天 / 本周 / 本月` 导航。
- 将 `运行概览` 改成可点击展开入口，Dashboard 默认不直接展示详细内容。
- 点击 `运行概览` 后再展示：`总消息数`、`Tool链运行`、实时图表、活跃排名。
- 活跃排名去掉头像，改为昵称与消息数同一行展示。
- 将时间刻度选项改为：`1小时 / 1天 / 1星期 / 1个月 / 4个月`。
- 将 Dashboard 中的重启系统入口移除，并把重启入口收进系统设置页。
- 后端 Dashboard 路由补充通用 `window_minutes` 支持，用于前端时间刻度窗口，不再受原先 `<= 60 分钟` 限制。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/pages/dashboard/components/RealTimeStats.tsx`
- `frontend/src/pages/dashboard/components/RankingList.tsx`
- `frontend/src/pages/settings/system.tsx`
- `frontend/src/services/api/dashboard.ts`
- `frontend/src/locales/zh-CN/dashboard.json`
- `frontend/src/locales/en-US/dashboard.json`
- `frontend/src/locales/zh-CN/settings.json`
- `frontend/src/locales/en-US/settings.json`
- `holo_cortex_zero/routers/dashboard.py`

## 验证
- `cd /path/to/source-root/frontend && pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `ceb0a6a` `fix(frontend): move secondary nav into topbar`
