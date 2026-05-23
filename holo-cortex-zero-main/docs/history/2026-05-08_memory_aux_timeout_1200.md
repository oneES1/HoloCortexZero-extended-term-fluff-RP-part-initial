# 2026-05-08 memory auxiliary timeout 1200s

## 背景

`auto_memory` 与 `memory_manage` 是后台记忆链路，不应使用主对话或快判定链路的短等待策略。

本轮目标是仅放宽这两条记忆辅助 LLM 调用到 `1200s`，不扩大到主 LLM、timeline、subconscious 或 ai_reply judge。

## 修改

- `holo_cortex_zero/services/memory/mem0_utils.py`
  - `memory_manage` 调用 `generate_auxiliary(...)` 的 `timeout` 从 `120.0` 改为 `1200.0`。
- `holo_cortex_zero/services/memory/auto_memory.py`
  - `auto_memory` 调用 `generate_prepared_auxiliary(...)` 的 `timeout` 从 `120.0` 改为 `1200.0`。
- `holo_cortex_zero/services/llm/responses.py`
  - `/responses` 非流式通用主干尊重上层显式传入的大于 `RESPONSES_TOTAL_TIMEOUT_SECONDS` 的超时。
  - 默认仍保留原有非流式超时策略：通用 `RESPONSES_TOTAL_TIMEOUT_SECONDS=800.0`，Uni Qwen 非流式特例 `50.0`。
  - 因此未显式传大于 `800.0` 的主 LLM 路径不被抬高到 `1200s`。

## 影响面

- `chat.completions` 与 `gemini` emitter 已直接使用调用点传入的 `timeout`，两条记忆链路实际为 `1200s`。
- `/responses` 非流式在调用点传入 `1200.0` 时实际为 `1200s`。
- `/responses` 非流式未显式传大于 `800.0` 的 timeout 时仍按原默认策略运行：通用 `800s`，Uni Qwen 非流式特例 `50s`。
- `timeline` 仍保持 `120.0`。
- `subconscious` 外层仍由 `SUBCONSCIOUS_TIMEOUT_SECONDS` 控制，默认 `15.0s`。
- `ai_reply judge` 外层仍由 `AI_REPLY_JUDGE_TIMEOUT_SECONDS` 控制，默认 `12s`。

## 回滚点

- 修改前快照提交：`18b89fc backup(llm): snapshot existing router cache changes`
- 回滚本轮只需还原本日志与上述三个代码文件中的 timeout 修改。
