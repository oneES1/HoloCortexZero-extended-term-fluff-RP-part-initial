# 2026-04-02 Uni chat 发射器缓存分支处理

## 背景

- 当前主 `chat.completions` 发射器会透传 `extra_params`，但不会消费 `GenerationRequest.cache_hints`。
- `/responses` 主干已具备缓存提示处理能力；`chat.completions` 主干缺少对应钩子。
- 目标是对 `hk.uniapi.io` 的 `chat.completions` 链路补一个最小分支兼容，不伤其他 chat 发射链路。

## 本次修改

- 文件：`holo_cortex_zero/services/llm/openai_chat.py`
- 新增 chat 主干缓存钩子：统一解析 `cache_hints.cache_control` 与 `stable_prefix`。
- 新增通用锚点选择逻辑：优先 `stable_prefix=system_first_text`，否则退回 message-boundary。
- 新增 Uni 分支兼容映射：仅当目标 host 为 `hk.uniapi.io` 时，将选中的锚点映射为 content block `cache_control`。
- 保留用户显式传入的 `payload.cache_control` 或内容块 `cache_control`，不覆盖已有请求语义。

## 主干 / 分支关系

- 主干：chat 发射器统一根据 `cache_hints` 选择缓存锚点。
- 分支兼容：仅已知兼容 content-block `cache_control` 的目标执行 wire-level 映射；当前实现命中 `hk.uniapi.io`。
- 未命中兼容目标时，仅记录锚点选择日志，不改写 wire payload。

## 真实 API 验证

代理：

- `HTTP_PROXY=http://<LOCAL_HTTP_PROXY>`
- `HTTPS_PROXY=http://<LOCAL_HTTP_PROXY>`

验证方式：直接调用 `OpenAIChatEmitter.generate(...)`，并传入：

- `cache_hints={"cache_control": "ephemeral", "stable_prefix": "system_first_text"}`
- `base_url=https://hk.uniapi.io/v1`
- `proxy=http://<LOCAL_HTTP_PROXY>`

验证结果：

1. `qwen3.5-plus`
   - 日志命中：`[openai_chat][cache] cache hint compatibility applied`
   - 返回文本：`OK`
   - `finish_reason=stop`
   - `usage.prompt_tokens_details.cache_type=ephemeral`

2. `deepseek-v3.2#thinking`
   - 日志命中：`[openai_chat][cache] cache hint compatibility applied`
   - 返回文本：`TEST_OK`
   - `finish_reason=stop`

## 风险说明

- 当前 `chat.completions` 的 content-block `cache_control` 兼容目标仅放宽到 host 级别：`hk.uniapi.io`。
- 若 Uni 后续对某些模型做了差异化限制，最坏情况是该模型忽略该字段或返回 4xx；当前双模型实测通过。
- 未改 docker 运行态；本次仅完成源码修改与真实 API 侧请求验证。

## 默认策略调整

- 已恢复 `ContextAssembler` 的默认 `cache_hints` 注入，避免误伤 `/responses` 与其它共用链路。
- `openai_chat` 中刚新增的 `hk.uniapi.io` content-block `cache_control` 自动映射现已默认关闭。
- 当前仅保留“保留已有显式 `cache_control`”的行为；不再因为默认 `cache_hints` 自动触发 Uni chat 缓存分支。
