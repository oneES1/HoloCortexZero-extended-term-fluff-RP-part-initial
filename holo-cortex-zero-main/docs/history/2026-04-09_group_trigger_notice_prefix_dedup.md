# 2026-04-09 群聊触发上下文前缀去重

## 背景
- 群聊触发回复时，模型看到的文本主干采用 `¥昵称¥YYYY-MM-DD HH:MM:SS¥ID¥说：` 作为系统运行状态符。
- 触发补语义前缀此前额外写入 `XXX@你；`。
- 两层同时包含发送者昵称后，会出现类似 `¥<SENDER_NAME>¥时间¥<SENDER_NUMERIC_ID>¥说：<SENDER_NAME>@你；isittrue` 的重复表达。

## 问题分析
- `context_window.manager._build_db_msg_prefix` 已经完整表达“是谁在说”。
- `message_service._build_group_trigger_notice_prefix` 再次带上发送者昵称，会让 `说：` 后面的正文出现重复人名。
- 该重复仅是群聊触发语义提示层的问题，不涉及主干身份表达、judge、上下文窗口路由或私聊逻辑。

## 最小修改
- 仅修改 `holo_cortex_zero/services/message_service.py`
- 将 `_build_group_trigger_notice_prefix()` 从返回 `XXX@你；` 改为固定返回 `@你；`
- 保持 `context_notice.prefix` 机制不变，保持 `¥昵称¥时间¥ID¥说：` 主干不变

## 修改后效果
- 旧格式：`¥<SENDER_NAME>¥2026-04-09 14:02:56¥<SENDER_NUMERIC_ID>¥说：<SENDER_NAME>@你；isittrue`
- 新格式：`¥<SENDER_NAME>¥2026-04-09 14:02:56¥<SENDER_NUMERIC_ID>¥说：@你；isittrue`

## 影响面
- 群聊 `@` / 关键词 / judge true 写入的 `context_notice.prefix` 会统一变为 `@你；`
- 不改原始聊天消息 `content_text`
- 不改上下文窗口锚定、用户身份、对话窗口与高级上下文窗口关系
- 不改私聊消息表现

## 风险与回滚
- 风险较低：若极少数旁路逻辑硬编码依赖 `XXX@你；` 文本样式，表现会变化
- 回滚点：恢复 `message_service._build_group_trigger_notice_prefix()` 原实现
