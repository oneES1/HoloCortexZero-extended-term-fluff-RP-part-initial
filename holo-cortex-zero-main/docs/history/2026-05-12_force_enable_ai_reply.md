# 2026-05-12 固定启用系统 ai_reply

## 背景

`AI_REPLY_ENABLED` 原本在 `message_service.py` 中控制系统 ai_reply 入口分支。关闭后会跳过新分支，回落到 legacy `should_trigger`，导致 `AI_REPLY_JUDGE_ENABLED` 即使开启也无法执行群聊 judge。

## 修改

- 后端消息入口固定走系统 ai_reply 主干，不再读取 `AI_REPLY_ENABLED` 决定是否启用。
- `AI_REPLY_ENABLED` 配置字段保留默认值 `True`，但标记 `is_hidden=True`，前端普通配置表不再展示。
- 初始化日志中的 `enabled` 固定打印运行态 `True`，避免配置残留值造成误判。
- `AI_REPLY_JUDGE_ENABLED` 未改动，继续作为群聊 LLM judge 子开关。

## 影响

- 历史配置里即使存在 `AI_REPLY_ENABLED=false`，运行态也会启用系统 ai_reply 入口。
- 群聊是否执行 judge 仍取决于 `AI_REPLY_JUDGE_ENABLED`、judge 激活窗口、prompt/model group/fail-open 配置。
- 高级用户多模态正则切组仍由 `AI_REPLY_MULTIMODAL_REGEX_ENABLED` 控制。

## 验证

```bash
uv run python -m compileall holo_cortex_zero/core/config.py holo_cortex_zero/services/message_service.py holo_cortex_zero/services/ai_reply/service.py
```
