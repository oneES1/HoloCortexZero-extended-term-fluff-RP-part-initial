# 2026-05-07 router canonical cache prefix

## 背景

- 多模态主链在路由层会先执行图片数量上限、旧图降级、图片物料化与兼容标准化。
- 旧逻辑只把 `cache_hints.stable_prefix` 粗略标成 `system_first_text`，无法表达图片限额后真实前缀在哪里断开。
- 当历史里同一张图片重复出现，或 `total=8 limit=4` 但实际重复引用较多时，单看图片数量会误判缓存可用范围。

## 修复

- 在 `LLMRouter` 的 `prepared_request` 阶段新增 canonical cache units：
  - 按最终 IR 顺序记录 turn / part 摘要。
  - 文本按完整文本 hash。
  - 图片按最终 url 或 materialized bytes hash。
  - tool call、reasoning replay、媒体降级状态纳入摘要。
- 每个 `context_id + protocol + base_url + model + extra_params + tools` 保存上一轮成功请求的摘要快照。
- 下一轮只做从头开始的最长公共前缀匹配，不做集合匹配，不按图片数量猜测。
- 将结果写回通用 `cache_hints`：
  - `stable_prefix=canonical_lcp`
  - `stable_prefix_units`
  - `stable_prefix_anchor_unit`
  - `stable_prefix_anchor_cacheable_index`
  - `stable_prefix_hash`
  - `stable_prefix_chars`
  - `stable_prefix_break_reason`
- 删除 `/responses` emitter 内部旧的 `ResponsesPrefixCache` 与 payload 级 LCP 主脑。
- `/responses` emitter 只消费 router 给出的 `stable_prefix_anchor_cacheable_index`，把它翻译成对应 `input_text` 的 `cache_control`。

## 行为

- 不改变图片限额策略；仍由现有逻辑决定保留哪些图片、降级哪些图片。
- 如果旧图片因限额从 image part 变成降级文本，LCP 会停在该位置之前。
- 如果 8 个图片引用里实际前 4 个最终 part 完全一致，LCP 会真实保留到第 4 个 part，而不是因为总数变化直接判无缓存。
- 快照只在模型调用成功返回后更新，超时或失败请求不会污染下一轮缓存判断。
- 所有正常经过 `LLMRouter.generate()` / `generate_stream()` 的协议共用同一套 LCP 判断，避免 `/responses` 和 chat/gemini 各自判断缓存边界。

## 验证

- `uv run python -m py_compile holo_cortex_zero/services/llm/router.py`
- `uv run python -m py_compile holo_cortex_zero/services/llm/router.py holo_cortex_zero/services/llm/responses.py`
- 使用三段 IR 直接验证：
  - 首轮 snapshot miss。
  - 相同重复图前缀加尾部文本时，`lcp_units=5`。
  - 图片在同一位置变成 `[图片超限降级: ...]` 文本时，`lcp_units=2`，断点为 `unit_type:part:image->part:text`。
- 使用 `/responses` payload 直接验证：
  - router 的 `stable_prefix_anchor_cacheable_index=1` 能正确挂到第二个 `input_text`。

## 回滚

- 回退 `holo_cortex_zero/services/llm/router.py` 中 canonical cache prefix 相关代码。
- 恢复 `holo_cortex_zero/services/llm/responses_prefix_cache.py` 及 `responses.py` 中旧的 payload 级 LCP 逻辑。
- 删除本日志文件。
