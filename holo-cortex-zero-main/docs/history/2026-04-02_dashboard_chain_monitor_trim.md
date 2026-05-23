# Dashboard 链条监测卡片再精简

## 本次调整
- 将右侧 `最新高级用户 Tool 链` 改名为更简洁的 `链条监测`。
- 增加简洁元信息：`触发原因（人 / 系统 / Judge）`、`当前上下文长度（按 token_input 摘要）`、`总耗时`。
- 移除逐事件耗时，避免重复展示不准确的时间分布；只保留总耗时。
- 链路事件改为极简摘要：模型只显示模型名，tool 只显示工具名和简短结果，reply 只显示简短回复，error 保留。
- `链条监测` 与 `最近红色报错日志` 改为左右并排，而不是上下堆叠。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/locales/zh-CN/dashboard.json`
- `frontend/src/locales/en-US/dashboard.json`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `b4840e3` `feat(dashboard): add trace and error summary panel`
