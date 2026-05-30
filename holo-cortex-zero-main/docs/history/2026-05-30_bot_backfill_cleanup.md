# 2026-05-30 bot 回填内容小 LLM 清理

## 背景

- 最终 bot 回复原本会在规则清理后写入框架上下文，历史同步链路也会把聊天表里的 bot 消息补成 `bot_sync`。
- 长回复对外发送需要保持完整，但写回上下文的 bot 文本会影响后续默认聊天风格，过长或过硬会污染轻量闲聊倾向。
- 本次目标是只清理“回填到框架上下文的 bot 文本”，不改变对外可见回复。

## 修改

- 新增系统配置：
  - `BOT_MESSAGE_BACKFILL_CLEANUP_ENABLED`
  - `BOT_MESSAGE_BACKFILL_CLEANUP_MODEL_GROUP`
  - `BOT_MESSAGE_BACKFILL_CLEANUP_THRESHOLD_CHARS`
- 新增 bot 回填清理服务：
  - 超阈值后用辅助聊天 LLM 把回填文本提炼为 40 字内短文本。
  - 清理结果入库前再次做规则清理、空白折叠和 40 字硬限制。
  - 超时、异常、模型组缺失或空结果时降级写入原规则清理文本。
- 辅助 LLM 走统一发射链路：
  - `aux_name=bot_backfill_cleanup`
  - `context_id=aux:bot_backfill_cleanup`
  - `cache_domain=bot_backfill_cleanup`
  - 不设置 `max_tokens`。
- 调整最终回复链路：
  - 对外发送完整文本。
  - 聊天表记录完整文本。
  - 仅上下文 `bot_reply` 回填走清理服务。
- 新一轮上下文组装前会 flush pending：
  - 清理未完成时立即降级写入原文本，保证最新 bot 内容不丢。
  - 清理完成后再到达的后台任务不会重复写入。
- 平台消息 ID 缺失时使用聊天表行 ID 生成去重键，减少后续 `bot_sync` 重复注入。

## 验证

- `python3 -m py_compile` 覆盖本次改动的后端模块，通过。
- `git diff --check` 通过。
- 前端静态包重新构建，通过。
- 主应用容器 recreate 后健康检查通过。
- WebUI 系统设置页可见新增配置项。

## 影响

- 开关默认关闭，关闭时保持旧行为。
- 开启后只影响写回框架上下文的 bot 文本，不改对外发送内容。
- 不处理人类原话、tool 结果、system 注入、memory 注入或历史旧长文本。
- 日志只记录触发与降级元信息，不记录待清理正文、清理后正文、密钥或端点。

## 风险 / 回滚点

- 风险集中在最终 bot 回复回填与下一轮上下文同步前的 pending flush。
- 若需回滚，撤销 bot 回填清理服务、系统配置项，以及最终回复链路中对该服务的调用。
