# 2026-05-22 DeepSeek 缓存命中观测与隔离修整

## 背景

- 现有工具链主调用经 `llm_router.call_with_fallback(...)` 走非流式请求，缓存命中观测主要依赖响应里的 `usage`。
- 观测层原先只识别 `prompt_tokens_details.cached_tokens` / `input_tokens_details.cached_tokens`，不会消费 DeepSeek 官方新增的 `prompt_cache_hit_tokens`。
- DeepSeek 官方 `chat.completions` 已改成自动上下文缓存；HCZ 需要继续维持自己的缓存命名空间隔离，但不能再受 UI `CACHE_TRANSPORT_PROFILE` 影响去下发显式 cache wire 字段。

## 本次修改

- 文件：`holo_cortex_zero/services/tools/chain_executor.py`
  - 在通用 usage 解析层补充识别：
    - `prompt_cache_hit_tokens` / `promptCacheHitTokens`
    - `prompt_cache_miss_tokens` / `promptCacheMissTokens`
  - 当供应商只返回 hit/miss 而未回填 `prompt_tokens_details.cached_tokens` 时：
    - `cached_tokens = prompt_cache_hit_tokens`
    - `prompt_tokens = prompt_cache_hit_tokens + prompt_cache_miss_tokens`
- 文件：`holo_cortex_zero/services/llm/openai_chat.py`
  - DeepSeek 官方 chat 分支前置绕开 `CACHE_TRANSPORT_PROFILE` 解析，不再因为 UI/profile 值触发显式缓存字段或 warning。
  - 新增 DeepSeek 官方缓存兼容整理：
    - 移除 `cache_control` / `prompt_cache_key` / `prompt_cache_retention` / `cache_prompt`
    - 流式请求强制 `stream_options.include_usage=true`
    - 将 HCZ 的 `context_id + cache_domain` 命名空间映射为 provider 侧 `user_id`，用于缓存隔离
  - SSE 解析层允许消费仅含 `usage` 的流片段，保证流式 DeepSeek 也能拿到缓存命中统计。

## 主干 / 分支关系

- 主干：
  - `cache_hints` 仍是框架统一缓存语义入口。
  - usage 统计仍在通用解析层归一到 `cached_tokens`。
- 分支兼容：
  - 仅 `api.deepseek.com` 的官方 chat wire 做 payload 清洗与 `user_id` 隔离映射。
  - 该映射复用 HCZ 已有的 `context_id` 与 `cache_domain` 命名空间，不引入新的用户概念，不改辅助 LLM `aux:<name>` 既有隔离方式。

## 验证点

- 非流式 usage 样例中，`prompt_cache_hit_tokens=800`、`prompt_cache_miss_tokens=200` 时，能归一得到：
  - `cached_tokens=800`
  - `prompt_tokens=1000`
- DeepSeek 官方 chat payload 中：
  - 不保留显式 cache transport 字段
  - 自动注入稳定 `user_id`
  - 流式请求补 `stream_options.include_usage=true`

## 风险说明

- 本次没有改动本地缓存快照 key，也没有更改上层 `cache_hints` 组装策略；影响面收敛在 usage 归一与 DeepSeek 官方 chat 发射器兼容层。
- 若后续其它供应商也采用 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` 命名，本次通用解析可直接复用；若字段语义不同，再按观测事实扩展。
