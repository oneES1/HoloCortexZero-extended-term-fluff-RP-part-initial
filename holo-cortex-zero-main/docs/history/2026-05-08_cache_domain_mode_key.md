# 2026-05-08 cache domain mode key

## 变更
- 在主对话请求的 `cache_hints` 中新增 `cache_domain`，由 `owner_type + effective_mode` 组成。
- `LLMRouter` 的前缀快照 key 纳入 `cache_domain`，用于把 `norm` / `deek` / `deep` 的缓存域拆开。

## 目的
- 保持同一上下文下不同模式的前缀缓存互不覆盖。
- 不改下游协议 wire，不改模型调用参数，仅调整本地快照分域。

## 验证
- 已通过 `python3 -m compileall`。
- 已通过 `uv run python` 逻辑验证：同一 context/model/base_url/tools/extra_params 下，`cache_domain=main:advanced:norm` 与 `cache_domain=main:advanced:deek` 生成的 router key 不同。

## 风险
- 仅影响本地前缀快照分域，不影响真实消息内容或 tool 解析。
- 若以后需要更细的 prompt 粒度隔离，可再把 `selected_prompt_key` 纳入 domain，但当前先按模式隔离。
