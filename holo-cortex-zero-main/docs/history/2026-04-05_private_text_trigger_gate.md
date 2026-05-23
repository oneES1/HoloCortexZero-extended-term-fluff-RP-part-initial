# 2026-04-05 私聊仅文本触发回复

## 问题现象

- 私聊链路里，只要消息进入 `push_human_message`，在 `AI_REPLY_ENABLED` 开启时就会直接调度 agent。
- 结果是纯图片、纯文件、纯音频、纯视频这类私聊消息，虽然本意只是接收附件，也会触发回复。

## 根因

- 根因在 `holo_cortex_zero/services/message_service.py` 的私聊直通分支。
- 旧逻辑只判断“是否私聊”，没有判断“这条私聊是否真的包含可触发的文本段”。
- `run_agent_v2` 会在执行时基于 `context_id` 更新锚点并同步当前 `chat_key` 的新消息，所以一旦被调度，就会启动本轮上下文组装。

## 本次规则

- 私聊只有在“存在非空文本段”时才触发回复。
- 文本 + 图片 / 文件 / 音频 / 视频：允许触发。
- 纯图片 / 纯文件 / 纯音频 / 纯视频 / 纯引用：不触发。
- 群聊触发逻辑不变。
- 附件接收、入库、后续被下一条文本消息吸收到上下文的机制不变。

## 实现方式

- 仅修改 `holo_cortex_zero/services/message_service.py`。
- 在 `MessageService` 内新增私聊触发文本判定：
  - 先看 `content_data` 是否存在 `type=text` 且 `text.strip()` 非空的消息段。
  - 若 `content_data` 为空，再回退到 `content_text.strip()`。
  - 若 `content_data` 非空但没有文本段，即便 `content_text` 中存在占位摘要，也不视为可触发文本。
- 在 `trigger_agent` 显式强触发分支之后、私聊直通分支之前，新增统一早退：
  - 私聊且无触发文本 → 已入库，但不调度 agent。

## 对 `context_id` / 锚点的影响

- `execution_key=context_id or chat_key` 的主干不变。
- 高级用户仍通过同一个 `context_id` 聚合上下文。
- 纯附件私聊因为不再触发调度，所以不会在这一轮更新 `active_dialog_id`，也不会误把回复窗口锚到该附件会话。
- 下一条真正的文本消息进入时，仍按原有 `context_id` 机制执行并完成上下文同步。

## 新增日志

- 私聊放行时记录 `has_trigger_text=True`。
- 私聊被拦截时记录：
  - `ctx`
  - `chat`
  - `owner_type`
  - `message_id`
  - `segment_types`
  - `content_text_len`
- 关键拦截日志文案：`私聊消息已入库但不触发回复，不启动本轮上下文组装`

## 验证步骤

### 静态校验

```bash
cd /path/to/source-root && python3 -m py_compile holo_cortex_zero/services/message_service.py
cd /path/to/source-root && uv run poe test
```

### 运行态同步

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero
```

### 人工验收

- TG 私聊发送纯图片：应入库，但不回复。
- TG 私聊发送纯文件 / 纯语音 / 纯视频：应入库，但不回复。
- TG 私聊发送文字 + 图片：应回复，且仍走原 `context_id`。
- TG 私聊发送仅引用无新文本：不回复。
- 群聊 mention / 关键词 / judge：保持原行为。

## 风险

- 若某个平台未来把“真实文本”错误地只写进 `content_text`，却没有同步到 `content_data` 的 `text` 段，那么这类私聊会被视为不可触发。
- 当前实现保留了 `content_data` 为空时对 `content_text` 的兜底，尽量降低该风险。
- 本次没有改适配器，不会引入供应商特化分支，但若后续新增适配器，需要继续遵守“文本必须落到标准 `text` 段”的主干约定。

## 回滚点

- 仅需回滚 `holo_cortex_zero/services/message_service.py` 本次新增的私聊文本判定与早退日志。
- 文档回滚点为 `docs/2026-04-05_private_text_trigger_gate.md`。
