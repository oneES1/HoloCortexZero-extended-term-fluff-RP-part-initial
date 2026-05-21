# 2026-04-05 触发上下文补语义前缀

## 背景
- 现状：回复上下文拼装时，模型能看到聊天文本，但不总能分清这次回复究竟是被谁触发、是否是系统内部唤醒。
- 问题：群聊里被 `@`、关键词、judge 命中的那条消息，进入上下文后只是普通聊天文本；系统内部触发（如系统消息、system inject）也缺少统一提示。
- 风险：模型可能把“当前要回复的触发消息”误判成普通历史，尤其在群聊与系统唤醒场景下语义不完整。

## 本次最小修改
- 在 `message_service.push_human_message` 中，当群聊消息以 `@`、关键词、judge 命中触发时，把触发前缀写入 `DBChatMessage.ext_data.context_notice.prefix`，格式为 `XXX@你；`。
- 在 `context_window.manager._db_msg_to_parts` 中读取 `context_notice.prefix`，只在上下文拼装时把前缀贴到原消息前，不污染原始 `content_text`。
- 在 `context_window.manager.get_history` 中，对 `system_inject` 统一补 `系统通知。` 前缀。
- 在 `message_service.push_system_message(trigger_agent=True)` 中，把系统通知直接注入上下文窗口，并优先透传 `ctx`，减少高级上下文下的系统触发丢语义问题。
- 在 `api/message.push_system` 中透传 `ctx` 到 `message_service.push_system_message`。

## 影响面分析
- 群聊直通触发：`@` / 关键词 / judge 命中的最新触发消息，会在模型看到的上下文里变成 `XXX@你；原文`。
- 私聊触发：普通私聊消息不加 `@你`，保持原样。
- 系统触发：system inject / push_system(trigger_agent=True) 进入模型上下文时会带 `系统通知。`。
- 原始聊天记录：`DBChatMessage.content_text` 仍保留原文，前缀只存在于上下文拼装层或 `ext_data` 元信息里。

## 涉及文件
- `holo_cortex_zero/services/message_service.py`
- `holo_cortex_zero/services/context_window/manager.py`
- `holo_cortex_zero/api/message.py`

## 回滚点
- 删除 `context_notice` 元数据写入与读取逻辑。
- 恢复 `push_system_message` 的旧调度路径（仅写 `DBChatMessage`，不注入 `DBContextMessage`）。
