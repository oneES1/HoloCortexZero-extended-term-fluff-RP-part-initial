# Tool链日志与 Channels 布局简化

## 本次调整
- Tool 链日志页移除页面标题、统计卡片、蓝色表头，以及原有状态/停止类型/触发用户/对话窗口/模型/耗时/轮次/时间等列展示。
- Tool 链日志列表改为单列折叠列表：默认展示 `时间 + 摘要`，展开后查看完整 trace 细节。
- Tool 链日志分页默认改为每页 `50` 条，分页选项调整为 `50 / 100`。
- Channels 桌面端左右区块对调：左侧为聊天选择列表，右侧为详情内容板。
- Channels 未选择聊天时，默认居中显示 `HCZ`，移除原先提示性警告/图标/按钮。

## 影响文件
- `frontend/src/pages/tool-traces/index.tsx`
- `frontend/src/pages/chat-channel/index.tsx`
- `docs/2026-04-03_tool_traces_and_channels_simplify.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`

## 风险与回滚点
- 风险：Tool 链日志首页信息密度明显下降，默认列表更简洁，但摘要依赖 `summary_text`；如为空则回退触发消息。
- 回滚点：本次提交完成后可直接按提交哈希回退。
