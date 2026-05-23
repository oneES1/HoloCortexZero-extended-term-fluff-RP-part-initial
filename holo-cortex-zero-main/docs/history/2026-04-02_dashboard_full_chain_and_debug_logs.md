# Dashboard 链路全量滚动与 Debug 日志纳入

## 本次调整
- `链条监测` 不再限制前 5 个事件，改为全量展示当前链路事件。
- 通过固定高度 + 内部滚动兜底，保证长链路不会撑坏 Dashboard。
- 日志面板从仅显示红错，调整为显示 `DEBUG / ERROR / CRITICAL / FATAL` 的历史日志流。
- 日志面板标题改为更准确的 `日志历史`。
- 日志卡片保持简洁摘要，点击可查看详情并复制完整内容。
- 继续保留自动滚动：用户停在底部时自动跟随；用户主动上滑查看历史时暂停自动滚动。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/locales/zh-CN/dashboard.json`
- `frontend/src/locales/en-US/dashboard.json`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `4f4dc07` `fix(logs): expand file tail window to 5mb`
