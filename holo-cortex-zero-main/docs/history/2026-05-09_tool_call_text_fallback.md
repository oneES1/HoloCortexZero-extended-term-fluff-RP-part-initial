# 2026-05-09 工具调用文本兜底修复

## 问题

- 现象：模型输出 `<|tool_call>call:seek{query: "DeepSeek 最新进展，2026年5月"}<tool_call|>` 时，聊天窗口直接收到该文本。
- 复现证据：修复前 `parse_qwen_tool_calls()` 对该文本返回 `tool_calls=0`，清理后文本仍为原文。
- 影响：该问题不是 `seek` 特化污染，而是文本工具调用方言未被转为标准 `ToolCall`，工具链随后按纯文本回复发送。

## 根因

- `holo_cortex_zero/services/llm/qwen_compat.py` 已支持标准字段、JSON/XML 标签、Qwen 原生 `<function=...>`、`<|tool_call|>{JSON}<|/tool_call|>`。
- 异常格式使用 `<|tool_call>` / `<tool_call|>` 标签，内容为 `call:name{key: value}`，既不是严格 JSON，也不是 `<function=...>`。
- `holo_cortex_zero/services/tools/chain_executor.py` 的未执行控制平面拦截也未覆盖 `<|tool_call>`，解析失败时无法阻止外发。

## 修改

- 在 `qwen_compat.py` 增加通用 `call:name{...}` 文本工具调用解析，输出标准 `ToolCall`。
- 参数解析仅做通用宽松对象解析：支持 `{query: "..."}` 转为 `{ "query": "..." }`，不对 `seek` 或任何供应商写特化分支。
- 在 `chain_executor.py` 补充 `<|tool_call>` / `<tool_call|>` 未执行控制平面检测，解析失败时丢弃并要求模型重新发起真实工具调用，避免污染聊天窗口。

## 验证

- 目标样例：`tool_calls=1`，`name=seek`，`arguments.query=DeepSeek 最新进展，2026年5月`，剩余文本为空。
- 兼容样例：`<|tool_call|>{"name":"seek","arguments":{"query":"x"}}<|/tool_call|>` 仍解析为 1 个工具调用。
- 非法控制平面残留：`<|tool_call>bad<tool_call|>` 被工具链识别为未执行控制平面文本，不会作为普通回复外发。

## 回滚点

- 修改前快照提交：`3febae5 backup(worktree): snapshot before tool call fallback fix`
- 行为提交可用 `git revert` 单独回滚本次 `fix` 提交。
