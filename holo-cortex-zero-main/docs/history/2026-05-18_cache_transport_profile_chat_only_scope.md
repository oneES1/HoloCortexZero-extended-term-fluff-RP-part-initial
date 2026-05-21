# 2026-05-18 cache transport profile chat-only scope

## 背景

- 2026-05-18 新增了模型组 `CACHE_TRANSPORT_PROFILE` 下拉，用于控制 `chat.completions` 请求侧缓存字段。
- 构造级排查发现：
  - `responses` emitter 不消费 `__hcz_cache_transport_profile`，该内部键会直接落进 `/responses` payload。
  - `gemini` emitter 也会把未知 `extra_params` 原样并入 payload，因此同样可能被新字段污染。
- 用户明确要求：`responses` 与 `gemini` 完全按本次任务前逻辑走，不受这次新增缓存配置影响。

## 本次最小修改

- `holo_cortex_zero/services/llm/responses.py`
  - 将 `__hcz_cache_transport_profile` 加入 `RESPONSES_TRANSPORT_CONTROL_KEYS`。
  - 结果：`/responses` 继续走既有主链缓存逻辑，不读取、不透传本次新增 chat 缓存配置。
- `holo_cortex_zero/services/llm/gemini.py`
  - 将 `__hcz_cache_transport_profile` 加入 `incompatible_keys` 清洗集合。
  - 结果：Gemini native payload 保持任务前行为，不携带新增内部缓存字段。

## 影响面

- `chat.completions`：保持 2026-05-18 新增能力不变。
- `/responses`：恢复为“仅既有 cache mainline + 既有 compat 分支”，不被模型组新缓存下拉干扰。
- `gemini`：继续只走 Gemini native 既有字段集，不受新缓存下拉干扰。

## 风险与回滚

- 风险低：仅增加两个 emitter 的内部字段清洗，不改路由、不改缓存主逻辑、不改已有 provider 兼容分支。
- 回滚点：撤销本文件记录对应的两个 emitter 清洗改动即可。
