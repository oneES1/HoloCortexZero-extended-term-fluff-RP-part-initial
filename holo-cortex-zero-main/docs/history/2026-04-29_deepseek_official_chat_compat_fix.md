# DeepSeek 官方 Chat 兼容修复（已被通用回放开关修订）

## 状态

本文档记录 2026-04-29 凌晨 DeepSeek 官方 chat 400 的第一阶段定位。后续已改为通用模型组开关方案，最新实现以 `docs/2026-04-29_reasoning_replay_model_group_switch.md` 为准。

## 重新核对后的结论

- DeepSeek 官方 chat thinking 开关为 `thinking={"type":"enabled|disabled"}`。
- DeepSeek 官方 chat thinking 强度使用顶层 `reasoning_effort`，当前兼容层会把通用 `reasoning.effort` 映射到该字段。
- thinking + tool_calls 的续链需要回放 assistant message 的 `reasoning_content`。
- DeepSeek 官方上下文缓存由服务端自动处理，本框架不再写显式 `cache_control` block。

官方参考：

- https://api-docs.deepseek.com/guides/thinking_mode
- https://api-docs.deepseek.com/guides/function_calling
- https://api-docs.deepseek.com/guides/kv_cache

## 当前实现

- 不再因为 native tools / tool history 自动关闭 DeepSeek thinking。
- DeepSeek 分支只处理官方 chat wire 参数差异：`reasoning.effort` → `reasoning_effort`，以及 text chat content 形态归一。
- 是否回放隐藏思考不再由 DeepSeek host 特判决定，而由模型组 `REPLAY_REASONING_CONTENT` 开关决定。
- 通用回放和跨协议工具续链细节见 `docs/2026-04-29_reasoning_replay_model_group_switch.md`。

## 过期内容说明

早期文档中“tool 场景强制关闭 thinking”“未新增 `reasoning_content` 持久化”的表述已过期，不再代表当前代码。

## 回滚

- 回滚 DeepSeek chat 参数兼容：回退对应代码提交。
- 关闭隐藏思考回放：在模型组配置中将 `REPLAY_REASONING_CONTENT=false` 后重启服务。
