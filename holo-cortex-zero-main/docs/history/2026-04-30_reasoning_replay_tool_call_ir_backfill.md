# 思维链回填 function call 顶层 IR 兜底

## 背景

用户侧出现 `所有 API 模型组均不可用，请稍后再试。`，线上日志显示：

- `2026-04-30 10:55:24` primary `deepseek-v4-pro` 在进入发射器前已经触发 `backfilled=1`。
- 同一请求仍对 `https://api.deepseek.com/v1/chat/completions` 返回 `400 Bad Request`。
- fallback `deepseek-v4-flash` 同样触发 `backfilled=1` 后仍返回 `400 Bad Request`。

真实失败 payload：

- `<CONTAINER_DATA_DIR>/logs/prompts/v2_request_chat_deepseek-v4-pro_20260430_105524_962720.json`
- `messages=47`
- `index=25` 是 assistant `tool_calls=1`，已带 `reasoning_content='。'`
- `index=26` 是 tool result
- `index=27` 是 tool 后 assistant 普通回复，缺 `reasoning_content`

## 复现实验

使用真实 `deepseek-v4-pro` API 做最小复现：

| 场景 | 结果 |
| --- | --- |
| assistant tool_call 缺 `reasoning_content` | `400`，错误：`The reasoning_content in the thinking mode must be passed back to the API.` |
| assistant tool_call 带 `reasoning_content='。'` | `200` |
| tool 前普通 assistant 缺 `reasoning_content`，tool_call 已带 `。` | `200` |
| tool_result 后普通 assistant 缺 `reasoning_content`，tool_call 已带 `。` | `400`，同样错误 |
| tool_result 后普通 assistant 带 `reasoning_content='。'` | `200` |

因此本质不是“所有历史 assistant 都必须补”，也不是“只补 assistant tool_call”。

本质是：开启思维链回填后，**function call 历史段内的 assistant 消息必须具备非空 `reasoning_content`**。function call 历史段从第一条 assistant tool_call 开始，包含后续 tool result 之后的 assistant 普通回复。

## 当前闭环

- `run_agent_v2._build_model_group_extra_params(...)` 在模型组开启 `REPLAY_REASONING_CONTENT` 时注入 `extra_params["replay_reasoning_content"] = True`。
- `LLMRouter.call_with_fallback(...)` 将 primary / fallback 模型组参数分别合并进 `GenerationRequest.extra_params`。
- 各协议发射器只按 `MessageTurn.reasoning_content` 做 wire 序列化，不负责决定内部信息流是否完整。
- `ToolChainExecutor._record_assistant_with_tool_calls(...)` 只在模型真实返回非空 `GenerationResult.reasoning_content` 时，将其保存到第一条 tool call 的 `_hcz_meta.reasoning_content`。
- `ContextWindowManager.get_history(...)` 只从历史 `_hcz_meta.reasoning_content` 恢复非空 `MessageTurn.reasoning_content`。

## 修复原则

本次修复只在顶层内部 IR 信息流兜底，不进入任何具体协议、不判断模型名、不判断供应商、不改发射器。

主干语义：

- 未开启 `replay_reasoning_content`：不动。
- tool 前普通 assistant：不动。
- 从第一条 assistant tool_call 或 tool result 开始，进入 function call 历史段。
- function call 历史段内任意 assistant 若缺失或全空白 `reasoning_content`，写入最小占位 `。`。
- 已有真实思维链时不覆盖。

## 修改

- `holo_cortex_zero/services/llm/router.py`
  - 保留 `LLMRouter.REASONING_REPLAY_TOOL_CALL_PLACEHOLDER = "。"`。
  - `LLMRouter._ensure_reasoning_replay_for_tool_calls(...)` 改为顺序扫描 `GenerationRequest.messages`。
  - 在 `generate(...)` 与 `generate_stream(...)` 的 `_prepare_request(...)` 后、进入 emitter 前统一调用。

该位置处于 router 顶层，能看到合并后的模型组 `extra_params`，且尚未进入 chat / responses / gemini wire 序列化。

## 验证

新增严格链式验证：

- `scripts/validation/validate_reasoning_replay_ir_backfill.py`

覆盖：

1. 不开回填组 tool 调用，不补。
2. tool 前普通 assistant 在回填组下仍不补。
3. 后接 UniQwen 有思维组回填组 tool 调用，旧空 tool 补 `。`，真实思维链不覆盖。
4. UniQwen 无思维组续接回复，tool_result 后普通 assistant 补 `。`。
5. 再不开回填组再 tool，不补。
6. 接回填 DeepSeek 组 tool，function call 历史段内空 assistant 均补 `。`。
7. 接有思维且回填 Gemini tool，并再调用 Gemini，Gemini envelope 保留，不被占位覆盖。

验证命令：

```bash
cd /path/to/source-root
uv run python -m py_compile holo_cortex_zero/services/llm/router.py scripts/validation/validate_reasoning_replay_ir_backfill.py
uv run python scripts/validation/validate_reasoning_replay_ir_backfill.py
```

## 风险与回滚

风险：开启回填且存在 function call 历史段的请求中，段内历史空 assistant 会被补一个 `。` 作为内部 reasoning 占位。该占位只在模型组明确开启 `REPLAY_REASONING_CONTENT` 时出现。

回滚点：回退本次提交即可；不涉及数据库迁移、不改配置、不清历史。

## 2026-04-30 追加：未开启回填禁止入库

要求：未开启 `REPLAY_REASONING_CONTENT` 的模型组，即使供应商响应里返回 `reasoning_content`，也禁止进入上下文记录。

修复点仍放在 `LLMRouter` 顶层出口：

- `LLMRouter._filter_result_reasoning_content(...)`
- `generate(...)` 返回前过滤。
- `generate_stream(...)` 每个 chunk yield 前过滤。

主干语义：

- `replay_reasoning_content=True`：允许 `GenerationResult.reasoning_content` 进入后续记录层。
- `replay_reasoning_content=False` 或缺失：清空 `GenerationResult.reasoning_content`，记录层无从保存。
- 不判断协议、不判断供应商、不改记录层分支。

验证命令追加：

```bash
cd /path/to/source-root
uv run python scripts/validation/validate_reasoning_persistence_gate.py
```
