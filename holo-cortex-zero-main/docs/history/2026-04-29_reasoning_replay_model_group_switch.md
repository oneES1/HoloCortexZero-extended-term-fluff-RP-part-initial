# Reasoning 回放模型组开关与跨协议工具续链

## 背景

本次修复目标不是为 DeepSeek 单独写一条并行主干，而是把“是否把模型返回的隐藏思考随 assistant tool_calls 回放”提升为模型组通用能力：`REPLAY_REASONING_CONTENT`。前端模型组高级配置负责开关，默认关闭；开启后由各协议 emitter 按自身 wire 形态落地。

重新核对的协议参考：

- DeepSeek Thinking Mode: https://api-docs.deepseek.com/guides/thinking_mode
- OpenAI Responses function calling / reasoning: https://platform.openai.com/docs/guides/function-calling?api-mode=responses
- Gemini Thought Signatures: https://ai.google.dev/gemini-api/docs/thought-signatures

## 当前主干

- `ModelConfigGroup.REPLAY_REASONING_CONTENT`
  - 前端模型组高级配置新增“回放思维链”开关。
  - `run_agent_v2._build_model_group_extra_params` 只在开关开启时注入 `replay_reasoning_content=true`。
- IR 与持久化
  - `MessageTurn.reasoning_content` / `GenerationResult.reasoning_content` 承载模型返回的隐藏思考。
  - `ToolCall.meta` 承载协议必要的 tool-call 隐藏元信息。
  - `tool_calls_json[]._hcz_meta` 复用现有 JSON 字段保存 hidden replay 元信息，不新增数据库表字段。
  - assistant 纯文本回复也会用 meta-only `tool_calls_json` 保存 `reasoning_content`；恢复历史时该 meta-only 记录不会被解析成伪 tool_call。
- 协议分支兼容
  - Chat-compatible：开关开启时把 `MessageTurn.reasoning_content` 回放为 assistant message 的 `reasoning_content`；关闭时剥离内部标记。
  - Responses：开关开启时回放 output 里的 `reasoning` item；同时保留 `function_call.id` 与 `call_id` 的区别，避免把 `call_*` 错写到 `id` 触发 400。
  - Gemini：开关开启时回放 `thoughtSignature`；Gemini tool schema 只在发射器内裁掉不支持的 `$schema` / `additionalProperties`。

## DeepSeek 官方分支

- 仍只做 DeepSeek 官方 chat wire 的参数形态兼容：`reasoning.effort` 映射为顶层 `reasoning_effort`，并按官方接受范围归一。
- 不再因为 native tools 或历史 tool 对话自动关闭 thinking。
- 不写显式 `cache_control` block；DeepSeek 官方上下文缓存按服务端自动策略处理。

## 验证

已执行静态验证：

```bash
cd /path/to/source-root
uv run python -m py_compile   holo_cortex_zero/schemas/ir.py   holo_cortex_zero/services/llm/router.py   holo_cortex_zero/services/tools/chain_executor.py   holo_cortex_zero/services/context_window/manager.py   holo_cortex_zero/services/llm/responses.py   holo_cortex_zero/services/llm/gemini.py
```

已执行离线 payload / 解析-持久化回放断言：

- Chat-compatible 开关开启才输出 `reasoning_content`，覆盖普通 assistant 文本历史与 assistant tool_calls 历史。
- meta-only `tool_calls_json` 只恢复 `reasoning_content`，不会生成空 tool_call。
- Responses 开关开启才回放 `reasoning` item，且无 `responses_item_id` 时不伪造 `function_call.id`。
- Gemini 开关开启才输出 `thoughtSignature`，并清理不兼容 tool schema 字段。
- `ToolCall.meta` 可通过 `tool_calls_json[]._hcz_meta` 持久化并还原。

已执行真实 wire 验证，结果文件：`/path/to/runtime-data/backups/validation/reasoning_replay_wire_20260429_073915.json`。

通过：15 / 15；本批排除本地 `qwen-3.5-27b`。

| 模型组 | 协议 | 结果 |
| --- | --- | --- |
| `deepseek-reason` | chat | 通过 |
| `Uni-3-flash-gemini` | gemini | 通过 |
| `Uni-deepseek3.2thinking` | responses | 通过 |
| `Uni-gemini-3-pro-image` | gemini | 通过 |
| `gpt-medium` | responses | 通过 |
| `gpt-high` | responses | 通过 |
| `Uni-qwen-3.5-plus` | chat | 通过 |
| `doubao` | responses | 通过 |
| `Uni-gemini-3.1-flash-img` | gemini | 通过 |
| `Uni-gemini-3.1-pro-preview` | gemini | 通过 |
| `Uni-grok-4.20-beta-0309-reasoning` | responses | 通过 |
| `Uni-grok-4-1-fast` | responses | 通过 |
| `Uni-3-flash-gemini-expensive` | gemini | 通过 |
| `deepseek-v4-pro` | chat | 通过 |
| `deepseek-v4-flash` | chat | 通过 |

## 风险与回滚

- 风险：开关应只给明确需要隐藏思考回放的思维链模型组开启；非思维链模型组默认关闭。
- 风险：Gemini 图片模型可能返回 tool_call 而非文本，这属于模型行为；本次验证目标是 wire 与工具续链不报错。
- 回滚代码：回退本次提交。
- 回滚运行态配置：把对应模型组的 `REPLAY_REASONING_CONTENT` 改回 `false` 并重启服务。


## text-form `<think>` 兜底

2026-04-29 追加：部分 Responses / OpenAI-compatible 网关不会返回 native `reasoning` item 或 `reasoning_content` 字段，而是把隐藏思考混在可见文本里。解析层现在统一提取以下形态并写入 `GenerationResult.reasoning_content`：

- `<think>hidden</think>visible`
- `visible<think>hidden</think>visible`
- `hidden</think>visible`
- `hidden<think>visible`（只有尾部 think 标记，且未必带 `/`）
- `<think>hidden`（缺失尾标签）

主干规则：先把隐藏思考从模型输出文本中提取出来，再让可见文本进入 tool-call 解析、用户回复和上下文保存；模型组 `REPLAY_REASONING_CONTENT` 开启时，Responses 协议会优先回放 native `reasoning` item，若只有 text-form hidden reasoning，则以 `<think>...</think>` assistant history 形式回填。该规则不绑定 Grok 或任何单一供应商。

## 跨协议 reasoning envelope

2026-04-29 追加：同一 context 在不同模型组、不同协议之间切换时，`reasoning_content` 不再直接混存 chat 纯文本、Responses JSON 或 Gemini JSON，而是在现有 `reasoning_content: str` 内统一写入 HCZ envelope；不新增数据库字段，不改 IR 主干。

主干 envelope：

- `protocol=hcz_reasoning_envelope`，`version=1`。
- `text` 保存可跨 chat / Responses 文本兜底复用的隐藏思考。
- `responses_items` 保存 Responses native `reasoning` output item。
- `gemini_thought_signatures` 保存 Gemini tool-call 续链需要的 `thoughtSignature`。
- `origin_protocol` 只记录来源，不参与分支特化决策。

回放规则：

- Chat-compatible 目标只读取 `text`，写入 assistant history 的 `reasoning_content`；不会把 Responses/Gemini 协议 JSON 当成 chat reasoning 发出。
- Responses 目标优先回放 native `responses_items`；如果只有 `text`，才以 `<think>...</think>` assistant history 形式回填；已有 native item 时不重复注入 text summary。
- Gemini 目标只在 tool-call 续链中读取 `gemini_thought_signatures`；没有签名时不伪造。

兼容读取：

- 旧纯文本 `reasoning_content` 按 envelope 的 `text` 使用。
- 旧 `{"protocol":"responses","items":[...]}` 按 `responses_items` 读取，并尽量从 `summary` 提取可跨协议的 `text`。
- 旧 `{"protocol":"gemini","thought_signatures":[...]}` 按 `gemini_thought_signatures` 读取。

验证命令：

```bash
cd /path/to/source-root
uv run python -m py_compile holo_cortex_zero/services/llm/reasoning_text.py holo_cortex_zero/services/llm/openai_chat.py holo_cortex_zero/services/llm/responses.py holo_cortex_zero/services/llm/gemini.py
```
