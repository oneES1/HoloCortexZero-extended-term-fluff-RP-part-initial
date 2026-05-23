# 2026-04-02 模型组显式协议开关 WIRE_API

## 背景

- 当前主聊天链与潜意识链都各自维护一份协议判定。
- 过去只能依赖自动推断，或在少数链路里通过 `EXTRA_BODY.wire_api` 做旧兼容。
- 当某个网关对 `/responses` 与 `/chat/completions` 的稳定性差异明显时，缺少一个**模型组级显式开关**，后续维护不方便。

## 本次修改

- 在模型组配置中新增字段：`WIRE_API`
  - 可选值：`default` / `chat` / `responses` / `gemini`
  - `default`：保持当前自动判定逻辑不变
  - 其他值：显式强制走对应协议
- 新增共享协议判定 helper：`detect_model_group_protocol()`
  - 主聊天链与潜意识链统一复用
  - 避免两处继续漂移出不同协议主干
- 兼容策略：
  - 主聊天链优先读取 `WIRE_API`，不额外放大旧 `EXTRA_BODY.wire_api` 的影响
  - 潜意识链保留对旧 `EXTRA_BODY.wire_api` 的兼容读取，避免已有隐式配置失效

## 当前运行态配置

- 已将 `Uni-qwen-3.5-plus` 显式设为：`WIRE_API: chat`
- 这只影响该模型组的协议选择，不改变其他模型组

## 影响说明

- 未配置 `WIRE_API` 或保留 `default` 的模型组，行为与原来一致
- 已显式配置 `WIRE_API` 的模型组，会稳定命中指定协议
- `CACHE_TRANSPORT_PROFILE` 继续表达传输/缓存偏好，不再承担“显式协议开关”的主职责

## 验证要点

- `WIRE_API=chat` 时，`Uni-qwen-3.5-plus` 的主聊天链会走 `chat.completions`
- 潜意识链与主聊天链对 `WIRE_API` 的优先级保持一致
- 对 `Uni-qwen-3.5-plus` 的 chat tool return 已做隔离验证，通过
