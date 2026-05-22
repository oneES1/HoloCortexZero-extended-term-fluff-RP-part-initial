# 2026-05-22 Tool 链 `llm_dump_id` 收尾未初始化修复

## 背景

- DeepSeek 官方 `chat.completions` 在高思考短回复场景下，可能返回 `reasoning_content` 但正文为空。
- Tool 链主流程会把这类结果当作空结果继续走错误/收尾路径。
- 现有 `ToolChainExecutor.run()` 里，`llm_dump_id` 只在成功拿到 `result` 后赋值，但 `finally` 的轨迹落库始终会写 `diagnostics.last_llm_dump_id`。
- 当主流程在 `llm_dump_id` 赋值前异常退出时，会额外触发 `UnboundLocalError`，把原本可观测的空结果/上游异常再次覆盖成框架自身崩溃。

## 本次修改

- 文件：`holo_cortex_zero/services/tools/chain_executor.py`
- 在 `run()` 的循环外初始化 `llm_dump_id = ""`。
- 保持原有语义不变：
  - 有真实 dump 时，后续仍会覆盖为本轮 dump id。
  - 没有 dump 时，轨迹里落空串，而不是在 `finally` 再次抛错。

## 主干 / 分支关系

- 主干：
  - Tool 链收尾落库必须容忍“本轮尚未形成完整 LLM 结果”的状态。
- 分支兼容：
  - 本次不修改 DeepSeek 协议处理，也不改变空结果判定策略。
  - 仅修复主干收尾变量生命周期，避免任意供应商的早退/异常路径都踩同一个未初始化变量。

## 验证点

- 复现条件：高思考 DeepSeek 官方 chat 请求返回空正文后，Tool 链不应再抛 `UnboundLocalError`。
- 轨迹落库时 `diagnostics.last_llm_dump_id`：
  - 有 dump 时保留真实值
  - 无 dump 时为空串

## 风险说明

- 这是单变量初始化修复，不改变模型路由、缓存语义、轨迹结构和外发逻辑。
- 若后续要优化“reasoning-only 结果是否应继续视为空结果”，那是独立策略问题，不属于本次修复范围。
