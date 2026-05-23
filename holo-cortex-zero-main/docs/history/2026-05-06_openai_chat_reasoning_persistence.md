# 2026-05-06 openai_chat 思维链落盘修复

## 结论
- `Tool Traces` 某些 `chat.completions` 链路看不到思维链，根因不是前端，而是 `openai_chat` 当时只落请求日志，不落响应日志。
- 对于未把 `reasoning_content` 直接写入 trace 的旧记录，系统缺少原始响应证据，无法稳定回填。
- 本次主干修复是给 `openai_chat` 增加响应落盘，并保持同一 `dump_id` 串联 request / response。

## 本次实证
- 样本 trace：`id=1986`
- `trigger_message_text`：`他们在开什么会`
- 原始 `trace_json` 中 `llm_rounds[0]` 与 `events[0]` 都没有 `reasoning_content`
- 对应请求日志存在：`v2_request_chat_qwen35-27b-mm-int4_20260506_231933_639274.json`
- 同时间戳响应日志不存在：`v2_response_*231933_639274*.json = 0`
- 因此旧记录即使“模型实际上有思维链”，当前运行态也没有可持久化证据供 Traces 读取

## 本次修改
- `holo_cortex_zero/services/llm/openai_chat.py`
  - `generate()`：请求落盘时拿到 `dump_id`，响应成功后追加 `dump_prompt_response(...)`
  - `generate_stream()`：请求落盘时拿到 `dump_id`，流式 chunk 逐段追加 `dump_prompt_response(..., suffix="stream")`
- 删除上次错误保留的脏改：
  - 不再保留 `tool_chain_executor` 直接写 trace reasoning 的错改残留
  - 不再保留 `tool-traces` 语言包里那两条误加文案残留

## 风险
- 风险低。
- 只新增 prompt 响应日志落盘，不改变模型协议、消息拼装、tool 执行、权限逻辑。
- 流式链路会增加若干 `v2_response_*_stream.json` 日志文件，但这是可追溯性所必需的持久化证据。

## 回滚点
- 如需回滚，撤销以下文件中的本次修改：
  - `holo_cortex_zero/services/llm/openai_chat.py`
  - `docs/2026-05-06_openai_chat_reasoning_persistence.md`
