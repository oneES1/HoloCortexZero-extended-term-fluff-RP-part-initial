# 2026-05-09 主模型组 LLM 单轮性能日志

## 背景

`deep/deek` 主模型组对话体感慢，需要区分：

- prompt 预填是否命中缓存；
- 命中缓存后是否仍慢在生成阶段；
- 每轮真实回复的 token 与耗时是否可复现追踪。

## 测试事实

- 运行态 `meromero-31b-resident` 指向 `qwen35-27b-mm-int4`，协议为 `chat`。
- 直连同前缀 24042 字测试：
  - 冷启动 `18.772s`，`cached_tokens=0 / prompt_tokens=14450`；
  - 热缓存 `3.573s` 与 `3.154s`，`cached_tokens=14444 / prompt_tokens=14450`。
- 框架 `LLMRouter -> openai_chat` 同路径测试：
  - 冷启动 `16.449s`，`cached_tokens=0`；
  - 热缓存 `0.945s` 与 `0.309s`，`cached_tokens=14443`。
- 带 tools 测试仍命中缓存：`cached_tokens=11089 / prompt_tokens=11095`。
- 插入一次不同 aux/timeline 请求后，主请求仍命中缓存：`cached_tokens=11038 / prompt_tokens=11044`。
- 流式首包测试：
  - 冷流式首包 `12.926s`，总耗时 `105.337s`；
  - 热流式首包 `0.792s / 0.351s`，总耗时仍 `51.490s / 44.161s`。

结论：模型端缓存本身有效；体感慢需要用主链日志继续确认是否慢在生成、输出长度、工具链等待或前缀偶发断裂。

## 变更

- `ToolChainExecutor._extract_usage_metrics()` 增加 `cached_tokens` 提取：
  - 支持 `prompt_tokens_details.cached_tokens`；
  - 支持 `prompt_tokens_details.cachedTokens`；
  - 支持 `input_tokens_details.cached_tokens/cachedTokens`。
- 每轮 LLM 调用完成后新增一条日志：`Tool 链 LLM 单轮性能`。
- 日志字段：
  - `context`
  - `iter`
  - `model`
  - `duration_ms`
  - `prompt_tokens`
  - `cached_tokens`
  - `cache_ratio`
  - `completion_tokens`
  - `total_tokens`
  - `text_length`
  - `tool_call_count`
  - `finish_reason`
  - `dump_id`

## 验证方式

在 QQ/TG 连续发送 3 条短消息后，用非全量日志读取：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml logs --tail=500 holo_cortex_zero 2>/dev/null | rg 'Tool 链 LLM 单轮性能|cached_tokens|cache_ratio'
```

判断标准：

- `cached_tokens > 0` 且 `cache_ratio` 高，但 `duration_ms` 仍高：慢在生成或链路等待。
- 连续 `cached_tokens=0`：继续排查稳定前缀断裂或模式/cache_domain 切换。
- `completion_tokens` 或 `text_length` 高：优先考虑缩短 deep/deek 输出或降低模型组输出上限。

## 风险与回滚

- 风险低：只增加日志和 usage 解析，不改变 LLM 请求、缓存字段、tool 调用、发送逻辑。
- 回滚点：撤回 `holo_cortex_zero/services/tools/chain_executor.py` 中本次日志与 `cached_tokens` 提取改动，并删除本文档。
