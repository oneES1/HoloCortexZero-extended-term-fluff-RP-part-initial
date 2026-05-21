# 2026-04-28 DeepSeek 官方 chat 缓存分支

## 背景

- `deepseek-v4-pro` 运行态模型组使用 `WIRE_API: chat`，请求进入 `openai_chat.py` 的 `chat.completions` 主链。
- 上层 `ContextAssembler` 已注入通用 `cache_hints`，但 chat 发射器此前没有对 DeepSeek 官方地址映射缓存 wire 字段。
- 用户要求避免复杂 profile/前端方案，改为只识别 DeepSeek 官方 chat 目标做最小缓存分支。

## 本次修改

- 文件：`holo_cortex_zero/services/llm/openai_chat.py`
- 新增 DeepSeek 官方 chat 缓存目标识别：`api.deepseek.com`。
- 保持主干仍由 `cache_hints` 驱动，复用现有通用锚点选择逻辑。
- 仅当目标 host 为 `api.deepseek.com` 且存在 `cache_hints.cache_control=ephemeral` 时，把选中的稳定 text block 映射为 `cache_control={"type":"ephemeral"}`。
- 命中日志使用 `[openai_chat][cache][deepseek_official]` 前缀，便于和其它 chat 目标区分。

## 边界

- 不修改前端。
- 不修改模型组配置。
- 不改 `WIRE_API` / `CACHE_TRANSPORT_PROFILE` 语义。
- 不影响 `/responses` 主链和 Uni-Grok `prompt_cache_key` 分支。
- 不重新启用 UniAPI chat content-block cache 分支，因此 `qwen3.5-plus` 等 UniAPI chat 模型不会新增 `cache_control`。
- 若 payload 已经存在 top-level 或 content-block `cache_control`，继续沿用现有保护逻辑，不覆盖用户显式字段。

## 验证

- 使用本地 payload 级验证，不联网、不烧 API。
- DeepSeek 官方 `https://api.deepseek.com/v1`：应在稳定 system text block 上出现 `cache_control={"type":"ephemeral"}`。
- UniAPI Qwen `https://api.uniapi.io/v1`：应保持无 `cache_control`，证明当前可用 qwen chat 路径未被误伤。
- 实测结果：
  - `deepseek-v4-pro` + `https://api.deepseek.com/v1`：`cache_control` 数量为 1，挂载在 system text block。
  - `qwen3.5-plus` + `https://api.uniapi.io/v1`：`cache_control` 数量为 0，system content 仍保持原始字符串。

## 风险与回滚

- 风险：若 DeepSeek 官方 chat 对 content-block `cache_control` 严格拒绝，则只影响 DeepSeek 官方 chat 请求，并由现有 fallback 接管。
- 回滚点：还原 `openai_chat.py` 本次 DeepSeek 官方分支改动并删除本文档。
