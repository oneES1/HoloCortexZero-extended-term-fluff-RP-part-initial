# Thinking 回放与上下文归零

## 背景

用户要求清空消息记录、context 归零，并通过前端模型组开关决定是否回放隐藏思考。该能力已从 DeepSeek 单点修复调整为通用模型组能力：`REPLAY_REASONING_CONTENT`。

## 数据归零

为避免旧历史里的 assistant tool_calls 缺少隐藏思考元信息继续污染工具续链，本次按要求清空消息/上下文记录后从零开始。执行前已对 PostgreSQL 相关表做 timestamped CSV 备份：`/path/to/runtime-data/backups/context_reset_20260429_065717`。

目标表：

- `context_message`
- `context_dialog_state`
- `context_window`
- `chat_message`

执行后计数：四张表均为 `0`；重启 `holo_cortex_zero` 后服务状态为 `healthy`。

## 当前代码策略

- 通用开关：`REPLAY_REASONING_CONTENT`。
- Chat-compatible：回放 assistant `reasoning_content`。
- Responses：回放 `reasoning` output item，并保留 `function_call.id` / `call_id` 差异。
- Gemini：回放 `thoughtSignature`，并在 Gemini emitter 内清理不兼容 tool schema 字段。
- 详细验证与模型组结果见 `docs/2026-04-29_reasoning_replay_model_group_switch.md`。

## 风险与回滚

- 风险：清空消息/上下文会让 bot 对话上下文从零开始；记忆库、配置、tool_state 不在本次清空范围。
- 风险：旧聊天记录 CSV 备份仅用于人工恢复/审计，不自动回灌。
- 回滚代码：回退对应提交。
- 回滚数据：从本次备份目录中按需恢复 PostgreSQL 表。
