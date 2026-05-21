# Dashboard 链条监测改为历史堆叠

## 本次调整
- 删除 `链条监测` 顶部的 `原因` 标签，减少横向占位。
- 将 `上下文长度` 与 `总耗时` 收进每条链路头部，直接跟在模型名后展示。
- 仪表盘不再只取最近一次高级链路，改为把最近拉到的高级链路按 `create_time` 顺序堆叠展示。
- 每条链路保留自己的事件列表与错误摘要，并通过固定高度 + 内部滚动兜底长历史。
- 补齐 `noChainEvents` 文案键，避免空链路时出现缺失翻译。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/locales/zh-CN/dashboard.json`
- `frontend/src/locales/en-US/dashboard.json`
- `docs/2026-04-03_dashboard_trace_history_stack.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- 当前工作区未按用户要求创建新提交；如需回滚，优先参考上一版 dashboard 记录：`docs/2026-04-02_dashboard_chain_monitor_trim.md`
