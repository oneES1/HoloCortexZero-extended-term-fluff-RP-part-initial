# 2026-05-06 Tool Traces 思维链展示补齐

## 结论
- Tool Traces 详情页新增了“思维链内容”展示区。
- 即使当前没有回填到历史上下文，前端也会固定显示该区块，并用空状态文案明确提示“当前无思维链内容”。
- 这次不改正常运行逻辑，只补展示面和 trace 记录字段。

## 本次修改
- `frontend/src/pages/tool-traces/index.tsx`
  - 在 LLM 轮次卡片中新增思维链内容区块。
  - 解析 HCZ reasoning envelope，优先展示 `text`，否则回显原始 JSON 或纯文本。
  - 展开详情时懒加载 `tool-traces/log-content`，避免老 trace 仅靠列表快照丢失思维链。
- `frontend/src/services/api/tool-traces.ts`
  - 为 `llm_rounds` 与 `events` 增加可选 `reasoning_content` 字段类型。
- `holo_cortex_zero/services/tools/chain_executor.py`
  - 将 `result.reasoning_content` 作为只读 trace 字段写入 `llm_rounds` / `events`，不影响执行结果。
- `holo_cortex_zero/routers/tool_traces.py`
  - 当旧 trace 自身未落 `reasoning_content` 时，按 trace 时间与模型从 prompt 请求日志回填最近一轮思维链。
- `frontend/src/locales/zh-CN/tool-traces.json`
- `frontend/src/locales/en-US/tool-traces.json`
  - 补齐思维链标题与空状态文案。

## 风险
- 风险低。
- 仅增加 trace 数据字段与前端展示，不改变 tool 调用、回复发送、回填策略或权限逻辑。
- 老 trace 没有 `reasoning_content` 时，会显示空状态，不会报错。

## 回滚点
- 如需回滚，撤销以下文件中的本次修改：
  - `holo_cortex_zero/services/tools/chain_executor.py`
  - `frontend/src/pages/tool-traces/index.tsx`
  - `frontend/src/services/api/tool-traces.ts`
  - `frontend/src/locales/zh-CN/tool-traces.json`
  - `frontend/src/locales/en-US/tool-traces.json`
  - `docs/2026-05-06_tool_traces_reasoning_panel.md`
