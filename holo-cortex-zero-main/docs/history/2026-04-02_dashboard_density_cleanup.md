# Dashboard 面板密度再收口

## 本次调整
- 删除 dashboard 文案中残留未使用的 `success / failed / empty` 面板键。
- 将空态文案从“暂无高级用户 Tool 链记录”收紧为“暂无链路记录”。
- 将右侧错误日志标题收短为“红错历史”。
- 将链条监测与红错历史两张卡的内边距、列表间距再压缩一轮，减少视觉噪音。
- 触发原因的人类兜底文案从“高级用户”改为更中性的“用户”。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/locales/zh-CN/dashboard.json`
- `frontend/src/locales/en-US/dashboard.json`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `9d6a52b` `feat(dashboard): add error history stream`
