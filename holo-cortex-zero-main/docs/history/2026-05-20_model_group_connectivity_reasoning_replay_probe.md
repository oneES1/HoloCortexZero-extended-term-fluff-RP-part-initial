# 2026-05-20 模型组连通性测试纳入思维链回填验证

## 背景

模型组连通性测试已有固定验证流程：

1. 第一轮要求模型调用 `hcz_connectivity_probe`。
2. 校验返回的 tool call。
3. 把 assistant tool_call 与 tool result 回灌。
4. 第二轮要求模型返回最终确认。

本次要求不是改变该流程，而是在流程内验证 `REPLAY_REASONING_CONTENT` 的回填语义是否真正生效。

## 修改

- `holo_cortex_zero/services/llm/connectivity.py`
  - 新增 `_probe_reasoning_replay_request(...)`。
  - 第二轮请求发出前，复用现有 `LLMRouter._ensure_reasoning_replay_for_tool_calls(...)` 做 IR 级回填预检。
  - 当 `replay_reasoning_content=true` 且 assistant tool-call 历史回填后仍存在空 `reasoning_content` 时，连通性测试直接失败。
  - 保留原有双轮 tool-call 连通性流程，不新增供应商分支。
  - 成功 details 增加数值证据：
    - `reasoning_replay_enabled`
    - `first_reasoning_len`
    - `assistant_tool_turns`
    - `replayed_reasoning_min_len`
    - `replayed_reasoning_max_len`
    - `reasoning_replay_blank_tool_turns`
    - `reasoning_replay_backfilled`
    - `reasoning_replay_request_cloned`
- `scripts/validation/validate_connectivity_reasoning_replay_probe.py`
  - 新增不联网验证脚本，覆盖三种 IR 场景：
    - 未开启回填：保留空 reasoning，不判失败。
    - 开启回填且第一轮无真实 reasoning：回填占位，`blank_tool_turns=0`。
    - 开启回填且第一轮有真实 reasoning：保留真实内容，不覆盖。

## 验证

已执行：

```bash
cd /home/ubuntu/hcz-deploy/holo-cortex-zero-main
python3 -m py_compile holo_cortex_zero/services/llm/connectivity.py scripts/validation/validate_connectivity_reasoning_replay_probe.py scripts/validation/validate_reasoning_replay_ir_backfill.py
HTTP_PROXY=http://127.0.0.1:19192 HTTPS_PROXY=http://127.0.0.1:19192 uv run python scripts/validation/validate_reasoning_replay_ir_backfill.py
HTTP_PROXY=http://127.0.0.1:19192 HTTPS_PROXY=http://127.0.0.1:19192 uv run python scripts/validation/validate_connectivity_reasoning_replay_probe.py
```

结果：

- `OK reasoning replay IR backfill chain: function_assistant_turns=6 tool_turns=5 placeholder=4 real=2`
- `OK connectivity reasoning replay probe: no_replay_blank=1 blank_backfilled=True real_len=14`

## 影响范围

- 只影响模型组 chat 连通性测试的 details 与失败断言。
- 不影响 embedding / draw 连通性测试。
- 不修改 provider 协议发射器。
- 不修改真实请求的回填主干，只复用现有 router 回填逻辑做验证。

## 风险与回滚

风险：开启 `REPLAY_REASONING_CONTENT` 的模型组，如果现有 router 回填逻辑失效，连通性测试会失败。这是预期行为，因为该模型组声明了后续 tool 请求需要回放隐藏思考。

回滚点：回退本次提交即可；不涉及数据库迁移、不改配置。

## 2026-05-20 追加修正：测试请求必须使用回填后的 IR

复查发现第一版只在第二轮请求前执行了 IR 回填预检并返回 details，但第二轮 `llm_router.generate(...)` 仍传入原始 `second_request`。虽然 router 内部最终也会回填，但 connectivity 测试层没有把“测试证据”和“实际第二轮请求对象”绑定到同一个 IR，证明力度不够。

修正：

- `_probe_reasoning_replay_request(...)` 改为返回 `(prepared_request, details)`。
- `_probe_generation_group(...)` 第二轮直接使用 `prepared_second_request` 调用 `llm_router.generate(...)`。
- details 字段 `reasoning_replay_request_cloned` 改为 `reasoning_replay_request_prepared`，表达测试层实际拿到了回填后的请求对象。
- validation 增加对象级断言：
  - 未开启回填：`prepared_request is original_request`
  - 开启回填且第一轮无真实 reasoning：`prepared_request is not original_request`
  - 开启回填且已有真实 reasoning：`prepared_request is original_request`

追加验证结果：

- `OK connectivity reasoning replay probe: no_replay_blank=1 blank_backfilled=True blank_prepared=True real_len=14`
- `OK reasoning replay IR backfill chain: function_assistant_turns=6 tool_turns=5 placeholder=4 real=2`
