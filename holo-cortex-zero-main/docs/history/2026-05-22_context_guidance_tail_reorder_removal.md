# 2026-05-22 guidance 尾部挪位特判移除

## 背景

- `ContextAssembler.assemble()` 旧逻辑会在 `history[-1]` 为 `user` 时：
  - 先拼 `history[:-1]`
  - 再拼 `guidance`（记忆 / 内部环境标注 / 时间）
  - 最后把这条 `latest_user_turn` 挪到最末尾
- 这会把动态区拆成：
  - 历史尾巴前半
  - `guidance`
  - 最新 user
- 当前 DeepSeek 缓存排查中，用户明确要求把 `guidance` 视作动态长尾端块，不再把最新 user 挪到它后面。

## 修改

- 文件：`holo_cortex_zero/services/context_window/assembler.py`
- 删除“`history[-1]` 为 user 就把最后一条 user 挪到 guidance 后面”的特判。
- 现在统一顺序为：
  1. `system`
  2. `compressed_summary`
  3. `history`（完整保留）
  4. `guidance`

## 验证

### 静态

- `python3 -m py_compile holo_cortex_zero/services/context_window/assembler.py`

### DeepSeek 真实请求复核

- 使用真实复杂 payload 母体，改成新顺序（`guidance` 固定末尾），直接请求 `api.deepseek.com/v1/chat/completions`。
- 三段复核：
  1. `A`: 追加用户消息后首轮请求
  2. `B`: 下一轮继续动态长尾
  3. `C`: tool 结果回放后下一轮回复

- 观测事实：
  - `A`: `prompt_cache_hit_tokens=0`
  - `B`: `prompt_cache_hit_tokens=0`
  - `C`: `prompt_cache_hit_tokens=4480`

- 补充两跳 tool 链形态验证：
  - 第 1 跳：明确“查北京天气”后，模型真实返回 `tool_calls`
  - 第 2 跳：补入 `tool_result` 后，模型正常回复，但该跳 `prompt_cache_hit_tokens=0`

## 结论

- 本次改动严格满足“不要再把最后一条 user 挪到 guidance 后面”的排布要求。
- 真实 DeepSeek 验证显示：
  - 改动后 `guidance` 已固定为尾部动态块；
  - 但“有缓存”并不只由这一处决定，真实 tool 链第二跳仍可见 `hit=0`；
  - 第三跳回复链路已能看到 `hit=4480`。

## 风险 / 回滚点

- 风险面收敛在 `ContextAssembler.assemble()` 尾部顺序。
- 若需回滚，只撤销 `holo_cortex_zero/services/context_window/assembler.py` 本次改动，并删除本文档。
