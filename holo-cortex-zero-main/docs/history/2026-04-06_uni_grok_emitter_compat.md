# 2026-04-06 uni-grok 发射器兼容整理

## 背景

- 用户反馈 `Uni-grok-4.20-beta-0309-reasoning`、`Uni-grok-4-1-fast` 与当前框架发射器不兼容，希望优先走 `chat`，不行则接受 `responses`。
- 本次只给 `uni-grok` 增加单独兼容分支，不复制另一套并行主干。

## 当前逻辑梳理

- 运行态模型组里，这两个组已经显式配置为 `WIRE_API: chat`。
- 实测最小纯文本请求时：
  - `chat` 可返回正常文本；
  - `responses` 也可返回正常文本。
- 实测最小工具请求时：
  - `grok-4-1-fast` 在 `chat` 下可返回原生 `tool_calls`；
  - `grok-4.20-beta-0309-reasoning` 在 `chat` 下不会稳定返回原生 `tool_calls`，而是普通文本，导致框架工具主链无法可靠衔接。
- 复盘真实失败日志时发现两类根因：
  - `chat` 失败：真实 payload 内有 5 张 `image/gif`，UniAPI grok 链路报错“Downloaded response does not contain a valid JPG, PNG, or WebP image”。
  - `responses` 失败：`grok-4.20-beta-0309-reasoning` 组的 `REASONING_MODE=high` 被映射成 `reasoningEffort`，上游明确报“不支持 parameter reasoningEffort”。

## 本次修改

- 在 `holo_cortex_zero/services/llm/router.py` 增加 `uni-grok` 目标识别：`hk.uniapi.io + grok-*`。
- 在路由层新增单独兼容分支：
  - 纯文本请求仍尊重原来的 `chat`；
  - 仅当 `uni-grok + chat + tools` 时，自动切回 `responses` 主链，避免 chat 的工具调用不稳定影响主干。
- 在路由层统一图片物料化后，对 `uni-grok` 的 `image/gif` 做单点归一化：
  - 只把 GIF 转成 PNG；
  - 不改其他模型、不改其他图片格式。
- 在 `holo_cortex_zero/services/llm/responses.py` 的 `uni-grok` 分支兼容里，裁掉 `/responses` 当前不支持的显式推理控制：
  - 去掉 `reasoning`
  - 去掉 `thinking`
- 运行态配置已进一步收口：`Uni-grok-4.20-beta-0309-reasoning` 与 `Uni-grok-4-1-fast` 现固定 `WIRE_API: responses`，避免纯文本场景再落回较脆弱的 chat 路径。
- 两个 `uni-grok` 组的 `CACHE_TRANSPORT_PROFILE` 也已显式设为 `responses`，让 GUI 展示、路由偏好与 `/responses` 主链缓存语义保持一致。
- `/responses` 通用 stream idle timeout 已从 `7s` 提高到 `30s`，降低 UniAPI / Grok 首包偏慢时的误判超时。
- 基于 `/responses` 缓存探针结果，`uni-grok` 分支现改为：使用稳定的 `context_id + model + system_digest` 构造 `prompt_cache_key`，不再让随历史增长滚动的 `prefix_hash` 直接决定 key；同时剥离对该 relay 无效的 `cache_control` 字段。

## 主干 / 分支关系

- 主干仍然是：
  - 路由层统一做媒体物料化与限额；
  - `chat` / `responses` emitter 只处理协议差异。
- `uni-grok` 兼容分支只做两件供应商特异修正：
  - 工具请求从 `chat` 切到 `responses`；
  - GIF 转 PNG、剔除不支持的推理控制字段。
- 没有为 `uni-grok` 复制第二套工具主干或媒体主干。

## 验证结论

- 复打真实失败 payload：
  - 原始 `chat` payload：400，错误为 GIF 图片不被接受。
  - 原始 `responses` payload：400，错误为 `reasoningEffort` 不被接受。
- 对同一份真实复杂 payload 做“GIF -> PNG + 去 reasoning/thinking”后：
  - `grok-4.20-beta-0309-reasoning` 的 `responses` 请求返回 200；
  - `grok-4-1-fast` 的 `responses` 请求返回 200。

## 风险与回滚

- 风险：
  - `uni-grok + tools` 现在会优先走 `responses`，与用户在 GUI 里显式配置的 `chat` 存在局部兼容覆盖关系。
  - GIF 转 PNG 会丢失动画信息，只保留静态画面；但这比整条请求 400 更可控。
- 回滚点：
  - 删除 `router.py` 中的 `uni-grok` 协议切换与 GIF 归一化逻辑；
  - 删除 `responses.py` 中 `drop:reasoning@uni_grok` / `drop:thinking@uni_grok` 兼容裁剪。
