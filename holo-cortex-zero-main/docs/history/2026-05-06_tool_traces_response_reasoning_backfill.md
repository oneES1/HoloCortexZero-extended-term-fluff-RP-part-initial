# 2026-05-06 Tool Traces 从 response 日志回填思维链

## 结论
- `Tool Traces` 之前只能从 `request` 日志回填旧 trace 的思维链，这对 `chat.completions` 某些模型不成立。
- 新证据表明：有些链路的真实思维链只出现在 `v2_response_*.json`，并不在 `request.messages[*].reasoning_content` 中。
- 本次修复把 `response` 日志也纳入回填来源，优先补齐旧 trace 的 `llm` 事件思维链展示。

## 本次实证
- 旧样本 `id=1986`：原始 `trace_json` 中没有 `reasoning_content`
- 对应 request 日志：`v2_request_chat_qwen35-27b-mm-int4_20260506_231933_639274.json`
  - 有 `reasoning: {"effort":"low"}`
  - 没有 `messages[*].reasoning_content`
- 对应 response 日志：`v2_response_chat_qwen35-27b-mm-int4_20260506_234313_464044.json`
  - `choices[0].message.reasoning_content` 存在
- 说明旧的“只扫 request”策略证据链不完整，必须同时扫 response

## 本次修改
- `holo_cortex_zero/routers/tool_traces.py`
  - 新增 response payload 的 `reasoning_content` 提取逻辑
  - 回填候选从 `v2_request_*` 扩展到 `v2_response_*`
  - request 继续按触发词过滤；response 直接按时间窗 + 模型匹配补 reasoning

## 风险
- 风险低。
- 只影响 `tool-traces/log-content` 的详情回填，不改变模型调用、消息存储、权限或实际回复。
- 若同时间窗内存在多个相同模型 response 文件，仍可能有误匹配风险；当前主干先按时间窗和模型收口，后续若要继续提高精度，再考虑补 trace ↔ dump_id 显式关联。

## 回滚点
- 如需回滚，撤销以下文件中的本次修改：
  - `holo_cortex_zero/routers/tool_traces.py`
  - `docs/2026-05-06_tool_traces_response_reasoning_backfill.md`

## 精确 dump_id 主链路收口

- 目标：只修复 Tool Traces 前端展示思维链，不改变 LLM 调用、历史上下文写入或 replay_reasoning_content 回填语义。
- 根因：旧 trace_json 没有可证明的 response dump 精确关联；按时间窗口/模型名扫描 prompt log 会错绑相邻 trace。
- 修改：GenerationResult 增加 dump_id；chat/responses/gemini emitter 把 request/response dump 的同一 dump_id 返回给 Tool 链；Tool 链把 dump_id 写入 llm_rounds/events。
- 展示：tool-traces log-content 仅按每轮 dump_id 读取 v2_response_{dump_id}.json，并从 chat choices、Responses output reasoning、Gemini thoughtSignature/ thought parts 提取展示用 reasoning_content。
- 边界：不修改 holo_cortex_zero/services/llm/router.py；不新增时间窗口兜底；无 dump_id 的旧 trace 不再猜测回填。
- 验证：python3 -m py_compile 通过目标后端文件。
