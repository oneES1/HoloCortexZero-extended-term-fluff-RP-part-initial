# 2026-04-27 上下文人类消息归属后缀

## 背景

聊天上下文原本依赖 `¥昵称¥YYYY-MM-DD HH:MM:SS¥ID¥说：` 标识发送者、时间与用户 ID。该运行前缀必须保留，但在长上下文和多模态消息中，仅靠前缀对模型来说有时不够醒目。

本轮只追加末尾归属标记，不替换旧前缀：

- 文本：`¥张三¥2026-04-27 12:00:00¥123¥说：你好**张三发的信息**`
- 图片：`张三发送的图**张三发的信息**` + image part

## 严格边界

追加 `**XXX发的信息**` 的范围：

- 普通 context：所有人类用户消息
- 高级 context：群聊里的普通用户消息
- 覆盖文本正文与图片/音频/视频/文件的媒体说明文本

不追加的范围：

- 高级 context 中的高级用户本人
- bot 历史消息
- system / system_inject / tool 消息
- 引用消息头与引用媒体
- 旧 `DBContextMessage`、旧压缩摘要、旧较早历史归档

## 实现说明

改动集中在 `holo_cortex_zero/services/context_window/manager.py` 的聊天消息同步主干：

- `sync_new_chat_messages()` 对每条人类 `DBChatMessage` 计算一次是否追加归属后缀
- `_db_msg_to_parts()` 保留 `¥...说：` 前缀，只在正文末尾追加后缀
- `_build_media_notice()` 在允许时给媒体说明末尾追加后缀
- `_db_msg_to_parts_bot()` 未改动，bot 不会获得 `**海菜子发的信息**`
- `_determine_role_for_db_msg()` 未改动，高级 context 的 user/assistant 分流保持原样

## 风险

- 新注入的符合条件的人类历史消息会多出 Markdown 加粗后缀，主模型 prompt 需要明确说明不要模仿该格式。
- 旧历史不会被批量回写，因此短期内同一 context 可能同时存在旧无后缀消息和新有后缀消息。
- 引用消息默认不追加，避免把被引用者误判为当前发言者；如后续需要覆盖引用，必须单独评估。

## 回滚点

如需回滚，撤销以下文件中的本次修改：

- `holo_cortex_zero/services/context_window/manager.py`
- `docs/2026-04-27_context_sender_attribution_suffix.md`
