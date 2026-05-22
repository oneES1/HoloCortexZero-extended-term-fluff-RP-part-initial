# 2026-05-22 Tool Trace 缓存 usage 原文透传与鲁棒展示

## 背景

- Tool trace 当前只把网关返回的 `usage` 归一成：
  - `prompt_tokens`
  - `completion_tokens`
  - `total_tokens`
  - `cached_tokens`
- 这能满足统一缓存率统计，但会吞掉网关原始 usage 里的其他缓存字段。
- 结果是：
  - 后端 trace 落库后丢失原始 usage 细节。
  - 前端 UI 只能看到归一后的 `cached_tokens`，看不到网关真实返回的 cache 统计原文。

## 本次修改

- 文件：`holo_cortex_zero/services/tools/chain_executor.py`
  - 将 usage 解析改为递归扫描嵌套 dict/list，兼容更多缓存统计字段：
    - `cached_tokens` / `cachedTokens`
    - `prompt_cache_hit_tokens` / `promptCacheHitTokens`
    - `prompt_cache_miss_tokens` / `promptCacheMissTokens`
    - `cache_read_input_tokens` / `cacheReadInputTokens`
    - `input_cached_tokens` / `inputCachedTokens`
    - `cachedContentTokenCount`
  - 保留原有统一主干：
    - 继续归一输出 `prompt_tokens / completion_tokens / total_tokens / cached_tokens`
  - 在 trace 事件里新增 `usage.raw_usage`：
    - 只要网关返回了 `usage` dict，就原样按 JSON 兼容值透传进 trace
    - 不再在 trace 链路里吞掉未知未来字段
- 文件：`frontend/src/services/api/tool-traces.ts`
  - 扩展 `ToolTraceUsage`，新增 `raw_usage`
- 文件：`frontend/src/pages/tool-traces/index.tsx`
  - 在每个 LLM 事件卡片内新增 `Gateway Usage` / `网关 Usage 原文` 区块
  - 原有缓存率与 token 汇总展示保持不变
- 文件：
  - `frontend/src/locales/zh-CN/tool-traces.json`
  - `frontend/src/locales/en-US/tool-traces.json`
  - 增补原文 usage 区块标题文案

## 主干 / 分支关系

- 主干：
  - usage 归一与 trace 落库仍走统一 `ToolChainExecutor` 主干
  - UI 仍优先使用统一的 `cached_tokens` 计算缓存率
- 分支兼容：
  - 不为 DeepSeek、Gemini、OpenAI 单独写新的 trace 主干
  - 仅在统一 usage 提取层放宽字段识别，并把原始 usage 一并保留

## 验证点

- DeepSeek 风格：
  - `prompt_cache_hit_tokens=1200`
  - `prompt_cache_miss_tokens=300`
  - 归一后应得到：
    - `cached_tokens=1200`
    - `prompt_tokens=1500`
- OpenAI 风格：
  - `prompt_tokens_details.cached_tokens=1200`
  - 仍能归一得到 `cached_tokens=1200`
- Gemini 风格：
  - `usageMetadata.cachedContentTokenCount=1200`
  - 仍能归一得到 `cached_tokens=1200`
- 任意未来网关若把缓存字段塞在更深层 dict/list 中：
  - trace `usage.raw_usage` 仍应完整保留并可在 UI 中查看

## 风险说明

- 本次不改 provider 发射协议，不改 DB schema，不改 trace API 结构主语义。
- 风险面收敛在：
  - usage 递归提取
  - trace 额外携带 `raw_usage`
  - 工具链详情页新增只读展示块
- 回滚点：
  - 撤回 `chain_executor.py` 的 usage 递归提取与 `raw_usage` 透传
  - 撤回前端 `raw_usage` 展示与类型定义
