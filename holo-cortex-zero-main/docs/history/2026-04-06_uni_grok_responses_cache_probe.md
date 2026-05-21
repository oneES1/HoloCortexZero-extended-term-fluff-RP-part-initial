# 2026-04-06 uni-grok responses 缓存格式探针

## 背景

- 用户确认当前上游网关没有出现预期的 `/responses` 缓存收益。
- 目标改为：不再重复烧钱验证同一配置，而是最小成本找出 `hk.uniapi.io + grok-4-1-fast-reasoning-latest` 在 `/responses` 下真正识别的缓存 wire 格式。
- 约束：只测 `responses`，不再测 `chat`。

## 本次探针设计

- 模型组：`Uni-grok-4-1-fast`
- 模型：`grok-4-1-fast-reasoning-latest`
- 地址：`https://hk.uniapi.io/v1/responses`
- 每种格式仅做两次：
  - 第一次冷请求
  - 第二次热请求
- 每种格式使用独立唯一前缀，避免不同格式之间互相污染缓存。

探测的 3 种 `responses` 变体：

1. `current_hcz`
   - 顶层 `cache_control={type:ephemeral}`
   - system content block 上也挂 `cache_control={type:ephemeral}`
2. `top_level_only`
   - 仅顶层 `cache_control={type:ephemeral}`
3. `prompt_cache_key_only`
   - 不挂 `cache_control`
   - 只传 `prompt_cache_key=<stable key>`

## 实测结果

### 1) `current_hcz`

- call1: `elapsed=8.209s`, `input_tokens=3975`, `input_tokens_details.cached_tokens=147`
- call2: `elapsed=5.304s`, `input_tokens=3975`, `input_tokens_details.cached_tokens=147`
- 结论：没有出现明显缓存命中增长，`prompt_cache_key` 回包为空。

### 2) `top_level_only`

- call1: `elapsed=9.547s`, `input_tokens=3972`, `input_tokens_details.cached_tokens=147`
- call2: `elapsed=3.727s`, `input_tokens=3972`, `input_tokens_details.cached_tokens=147`
- 结论：仍然没有出现缓存命中增长。

### 3) `prompt_cache_key_only`

- call1: `elapsed=6.655s`, `input_tokens=3976`, `input_tokens_details.cached_tokens=147`
- call2: `elapsed=4.993s`, `input_tokens=3976`, `input_tokens_details.cached_tokens=3970`
- 结论：第二次请求出现了几乎整段前缀都被缓存读取的现象。
- 同时回包中的 `prompt_cache_key` 也稳定回显：
  - `hcz-probe-prompt_cache_key_only_173ba02051b246ec83040e70cd877c6c`

## 结论

- 对 `hk.uniapi.io` 的 `grok-4-1-fast-reasoning-latest` 而言：
  - **当前 HCZ `/responses` 主链使用的 `cache_control` 方案并不是有效缓存格式**。
  - **有效格式是显式 `prompt_cache_key`**。
- 这说明该 relay 在 `responses` 下更像是“命名键缓存”而不是“OpenAI block cache_control 缓存”。

## 对主干的启示

- 主干仍应保留通用 `/responses` cache mainline，不为单个上游复制另一套并行主干。
- 分支兼容如果要接入 `uni-grok` 的真实缓存能力，应该走：
  - 主干继续负责统一 cache hint / prefix snapshot / anchor 选择
  - `uni-grok` 分支仅在 wire 层把“选中的稳定前缀”映射为 `prompt_cache_key`
- 当前还未改代码，只完成了格式识别。

## 建议的最小后续改造

- 为 `uni-grok + /responses` 增加一个**分支兼容映射**：
  - 从当前主干已经算出的稳定前缀信息，导出稳定 `prompt_cache_key`
  - 将该 key 注入 `/responses` payload
- 不建议继续对 `cache_control` 方案重复烧钱验证。

## 风险与回滚

- 本次仅新增实验记录文档，没有改运行时代码。
- 回滚点：删除本文档即可。
