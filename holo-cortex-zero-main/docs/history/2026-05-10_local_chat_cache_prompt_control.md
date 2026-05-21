# 2026-05-10 本地 Chat prompt cache 真控制与降级测试

## 背景

主模型组 `meromero-31b-resident` 经 OpenAI-compatible `chat.completions` 调用本地 qwen 服务。此前 router 只计算 `cache_hints` / LCP，但 `openai_chat` 对本地 chat 目标没有把缓存意图写入 wire payload。

## 变更

- `holo_cortex_zero/services/llm/openai_chat.py`
  - 当 `cache_hints.cache_control=ephemeral` 且目标是本地 `http://<LOCAL_OPENAI_COMPAT_HOST>:18081/v1` chat 服务时，在 payload 写入：
    - `cache_prompt=true`
  - 日志前缀：`[openai_chat][cache][local_chat] enabled prompt cache`

## 控制字段实测

运行态模型组：

- 模型组：`meromero-31b-resident`
- 模型：`qwen35-27b-mm-int4`
- Base URL：`http://<LOCAL_OPENAI_COMPAT_HOST>:18081/v1`

同一稳定前缀测试：

| 场景 | extra | 结果 |
| --- | --- | --- |
| 默认冷 | `{}` | `13.753s`, `cached_tokens=6 / prompt_tokens=8426` |
| 默认热 | `{}` | `3.375s`, `cached_tokens=8418 / prompt_tokens=8426` |
| 显式开缓存 | `{"cache_prompt": true}` | `3.057s`, `cached_tokens=8418 / prompt_tokens=8426` |
| 显式关缓存冷 | `{"cache_prompt": false}` | `12.931s`, `cached_tokens=0 / prompt_tokens=8426` |
| 显式关缓存热 | `{"cache_prompt": false}` | `11.436s`, `cached_tokens=0 / prompt_tokens=8426` |
| 固定 slot 热 | `{"id_slot": 0}` | `5.569s`, `cached_tokens=8418 / prompt_tokens=8426` |

结论：`cache_prompt` 是服务端真实识别的缓存开关。`cache_prompt=false` 可稳定关闭缓存，`cache_prompt=true` 可显式开启缓存。

## 降级测试链路

构造两轮请求：

1. 第一轮：`system稳定文本 + history稳定文本 + image_url + 尾部动态文本`
2. 第二轮：`system稳定文本 + history稳定文本 + 降级文本 + 尾部动态文本`
3. 第三轮：重复第二轮降级文本

### 禁用缓存对照组

- 第一轮原图：`id_slot=0, cache_prompt=false`
  - `13.986s`, `cached_tokens=0 / prompt_tokens=10526`
- 第二轮降级：`id_slot=0, cache_prompt=false`
  - `16.115s`, `cached_tokens=0 / prompt_tokens=10284`

### 启用缓存控制组

- 第一轮原图：`id_slot=0, cache_prompt=true`
  - `7.152s`, `cached_tokens=10237 / prompt_tokens=10526`
- 第二轮降级：`id_slot=0, cache_prompt=true`
  - `5.153s`, `cached_tokens=10237 / prompt_tokens=10284`
- 第三轮重复降级：`id_slot=0, cache_prompt=true`
  - `6.243s`, `cached_tokens=10279 / prompt_tokens=10286`

结论：原图变成降级文本时，模型端仍可复用降级点之前的稳定前缀；重复降级文本时可进一步接近全量命中。

## 风险与回滚

- 风险低：只在已有 `cache_hints.cache_control=ephemeral` 的请求上，对本地 chat 目标显式开启 prompt cache。
- 不改变 router LCP、上下文拼装、tools、发送逻辑。
- 回滚点：撤回 `openai_chat.py` 中 `[openai_chat][cache][local_chat]` 分支，并删除本文档。
