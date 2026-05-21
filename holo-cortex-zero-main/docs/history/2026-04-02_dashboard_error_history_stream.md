# Dashboard 红色错误日志改为历史流并可查看详情

## 本次调整
- 将 `原因` 文案从 `人 / 系统 / Judge` 改为更自然的 `系统发起 / <高级用户昵称>发起`。
- `链条监测` 与 `最近红色报错日志` 的宽度比例改为 `4:6`。
- 新增日志级别过滤主干：`/logs` 和 `get_log_records` 支持按 `levels` 过滤，避免为 dashboard 误拉非红错日志。
- `最近红色报错日志` 改为展示历史红错流：按时间顺序排列，支持用户滚动查看历史。
- 日志面板默认自动滚动到底部；当用户上滑查看历史时暂停自动滚动，回到底部后恢复自动跟随。
- 点击历史日志可查看详情，并支持复制完整报错信息；未点开前仅展示简洁摘要。

## 影响文件
- `holo_cortex_zero/core/logger.py`
- `holo_cortex_zero/routers/logs.py`
- `frontend/src/services/api/logs.ts`
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/locales/zh-CN/dashboard.json`
- `frontend/src/locales/en-US/dashboard.json`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `03f6533` `fix(dashboard): simplify chain monitor`
