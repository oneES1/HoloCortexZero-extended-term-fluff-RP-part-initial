# Dashboard 右侧主面板补充高级 Tool 链与错误日志

## 本次调整
- 在 Dashboard 主图右侧新增摘要面板，利用原本空出的空间承接“新东西”。
- 新增 `最新高级用户 Tool 链` 卡片：展示最近一轮 `permission_level=advanced` 的链路过程。
- 链路过程采用高颜值摘要样式展示，仅保留关键步骤、触发内容、时长和最近链路报错；详细信息仍留在 Tool Logs / Tool Traces 页面。
- 新增 `最近红色报错日志` 卡片：展示最近一条 ERROR/CRITICAL/FATAL 日志。
- 删除不再使用的 `RankingList.tsx`，避免重复维护。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/locales/zh-CN/dashboard.json`
- `frontend/src/locales/en-US/dashboard.json`
- 删除：`frontend/src/pages/dashboard/components/RankingList.tsx`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `d65ebe9` `fix(dashboard): anchor overview to chart`
