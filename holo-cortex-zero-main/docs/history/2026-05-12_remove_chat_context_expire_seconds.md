# 2026-05-12 删除对话上下文过期秒数字段

## 背景

`AI_CHAT_CONTEXT_EXPIRE_SECONDS` 的前端标题是“对话上下文过期时间 (秒)”，但当前主对话上下文已经由 context window、压缩阈值、硬上限和条数限制控制。

该字段实际只在 memory prompt inject 中限制 recent messages 的时间窗，语义已经残留。当前已有 `AI_CHAT_CONTEXT_MAX_LENGTH` 条数限制，足够控制 memory recent messages 的取样规模。

## 修改

- 删除 `CoreConfig.AI_CHAT_CONTEXT_EXPIRE_SECONDS`。
- 删除 memory runtime 中基于该字段计算的 `record_sta_timestamp`。
- memory recent messages 只按当前 chat 的 `conversation_start_time` 和 `AI_CHAT_CONTEXT_MAX_LENGTH` 取最近消息。
- 删除运行配置 `/path/to/runtime-data/configs/holo-cortex-zero.yaml` 中的 `AI_CHAT_CONTEXT_EXPIRE_SECONDS`。

## 验证

```bash
rg -n 'AI_CHAT_CONTEXT_EXPIRE_SECONDS|对话上下文过期时间|Context Expiration Time' holo_cortex_zero frontend/src frontend/dist /path/to/runtime-data/configs/holo-cortex-zero.yaml
uv run python -m compileall holo_cortex_zero/core/config.py holo_cortex_zero/services/memory/runtime.py
pnpm --dir frontend build
```
