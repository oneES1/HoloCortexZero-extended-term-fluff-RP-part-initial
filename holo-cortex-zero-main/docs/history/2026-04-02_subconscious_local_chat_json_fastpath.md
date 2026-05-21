# 2026-04-02 潜意识本地 chat 无工具快路

## 背景

- 本地 `qwen35-27b-mm-int4` 在 `/responses` 路径下即使传入关闭思维链语义，实测仍会持续产出 reasoning，且接近真实 Stage1 prompt 时延偏高。
- 同一实例在 `chat/completions` 路径下，使用 `chat_template_kwargs.enable_thinking=false` 可稳定关闭 thinking，并显著降低辅助路由类请求成本。
- 但当前潜意识 Stage1 默认偏向 tool-first；而这台本地 vLLM chat 未开启 native auto tool choice，最稳路线应改为“chat + 无工具 + 一行 JSON”。

## 本次修改

- `holo_cortex_zero/services/llm/openai_chat.py`
  - 为 `chat.completions` 增加 extra_params 规范化入口。
  - 主干保持统一语义：业务层仍只传 `thinking` 等通用字段。
  - 分支兼容仅在本地 vLLM chat 目标上，将 `thinking={type:disabled}` 改写为 `chat_template_kwargs.enable_thinking=false`。
  - 同时在发射前移除 `wire_api`、`skip_native_tools` 等运输控制字段，避免把内部路由参数透传给上游。

## 运行态配置

- 将 `SUBCONSCIOUS_MODEL` 切到 `qwen35-hcz-resident`。
- 为该模型组写入：
  - `wire_api=chat`
  - `skip_native_tools=true`
  - `thinking={type:disabled}`

## 预期效果

- 潜意识 Stage1 走本地 `chat/completions`。
- 不再依赖本地 native tool choice，直接输出一行 JSON 给现有解析主干。
- 关闭思维链，降低 Stage1 耗时并保持本地零外部调用成本。
