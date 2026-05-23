# 2026-04-06 uni-grok responses 缓存 TTL 探针

## 背景

- 用户要求在框架外部直接对上游网关做最小 TTL 实验。
- 目标：测 `hk.uniapi.io + grok-4-1-fast-reasoning-latest` 在 `/responses` + `prompt_cache_key` 下的缓存存活情况。
- 约束：只做 `1 / 3 / 5` 分钟三组、共 `6` 次请求，不额外重复烧钱。

## 实验设计

- 目标地址：`https://hk.uniapi.io/v1/responses`
- 模型：`grok-4-1-fast-reasoning-latest`
- 缓存格式：`prompt_cache_key`，不挂 `cache_control`
- 每组使用独立 `prompt_cache_key`
- 每组两次请求：
  - 第一次冷请求
  - 等待指定时长后第二次热请求

三组 key：

- `ttl_1m` → `hcz-ttl-ttlprobe_93369e4ba4-ttl_1m`
- `ttl_3m` → `hcz-ttl-ttlprobe_93369e4ba4-ttl_3m`
- `ttl_5m` → `hcz-ttl-ttlprobe_93369e4ba4-ttl_5m`

## 实测结果

### 冷请求

- `ttl_1m` call1：`cached_tokens_input=148`
- `ttl_3m` call1：`cached_tokens_input=147`
- `ttl_5m` call1：`cached_tokens_input=148`

这些基线都可以视为“未命中缓存”。

### 热请求

- `ttl_1m` call2：`cached_tokens_input=3963`
  - 结论：`1 分钟` 时明显命中缓存。
- `ttl_3m` call2：`cached_tokens_input=147`
  - 结论：`3 分钟` 这组没有命中缓存。
- `ttl_5m` call2：`cached_tokens_input=3963`
  - 结论：`5 分钟` 这组反而明显命中缓存。

## 结论

- 这组结果**不符合“单一固定 TTL”**的特征。
- 如果上游是一个简单固定 TTL：
  - `3 分钟` miss，`5 分钟` 就不应该再 hit。
- 但当前结果是：
  - `1 分钟` hit
  - `3 分钟` miss
  - `5 分钟` hit

因此更合理的判断是：

1. **上游缓存并非单一固定 TTL 模型**。
2. 更像是以下不可控因素之一：
   - 上游 relay 多实例 / 多分片，不同 key 可能落到不同缓存后端
   - 缓存存在容量淘汰 / 机会性回收，而不是严格按时间统一失效
   - 某些请求可能落到未共享缓存的实例，导致同 key 命中不稳定
3. 至少可以确认：
   - `prompt_cache_key` 格式本身是有效的
   - **缓存生存时间可以超过 5 分钟**
   - 但**命中稳定性不是严格可预测的**

## 对当前框架的意义

- 这说明当前“稳定 key”修复方向是正确的：
  - 我们已经把可控问题（key 漂移）修掉。
- 后续如果再出现缓存突然掉线：
  - 优先怀疑上游 relay 的缓存一致性 / 分片 / 淘汰策略
  - 而不是我们本地 key 再次滚动

## 风险与回滚

- 本次仅新增实验记录文档，没有改任何运行时代码。
- 回滚点：删除本文档即可。
