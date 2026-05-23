# 2026-05-18 模型组缓存格式可配置

## 背景

- `GenerationRequest.cache_hints` 是 HCZ 主干缓存意图入口。
- chat.completions 的 wire 字段并不统一：
  - 宽松网关可能接受顶层 `cache_control={"type":"ephemeral"}`。
  - OpenAI 官方格式使用 `prompt_cache_key` / `prompt_cache_retention`。
  - 本地 OpenAI-compatible 目标使用 `cache_prompt=True`。
- 不能把其中一种供应商字段写成新的并行主干。

## 修改

- 复用模型组已有 `CACHE_TRANSPORT_PROFILE` 字段，不新增并行配置。
- 默认值改为 `default`，表示保留当前现状策略。
- 模型组页新增“缓存格式”下拉：
  - `default`
  - `cache_control`
  - `prompt_cache_key`
  - `cache_prompt`
  - `off`
- `model_group_params` 把模型组缓存格式注入内部 extra param。
- `openai_chat` 根据该 profile 映射 chat wire 字段：
  - `default`：保留现状自动分支；普通未知 chat 目标继续按现状发顶层 `cache_control`。
  - `cache_control`：强制顶层 `cache_control={"type":"ephemeral"}`。
  - `prompt_cache_key`：强制 `prompt_cache_key` + `prompt_cache_retention="24h"`。
  - `cache_prompt`：强制 `cache_prompt=True`。
  - `off`：不写显式缓存字段。

## 验证

- 后端构造 payload 验证 5 种 profile：
  - `default` -> `{'cache_control': {'type': 'ephemeral'}}`
  - `cache_control` -> `{'cache_control': {'type': 'ephemeral'}}`
  - `prompt_cache_key` -> `{'prompt_cache_key': 'hcz-chat-...', 'prompt_cache_retention': '24h'}`
  - `cache_prompt` -> `{'cache_prompt': True}`
  - `off` -> `{}`
- `python3 -m compileall holo-cortex-zero-main/holo_cortex_zero/core/config.py holo-cortex-zero-main/holo_cortex_zero/services/llm/model_group_params.py holo-cortex-zero-main/holo_cortex_zero/services/llm/openai_chat.py`
  - 结果：通过。
- `pnpm --dir frontend build`
  - 结果：通过，`✓ built in 32.65s`。

## 风险与回滚点

- 风险：不同中转对 `prompt_cache_retention="24h"` 支持不一；该风险仅在用户显式选择 `prompt_cache_key` 时触发。普通未知 chat 目标默认仍沿用现状的 `cache_control` 风险面。
- 回滚点：撤销本次 `CACHE_TRANSPORT_PROFILE` 注入、`openai_chat` profile 分支和前端下拉。
