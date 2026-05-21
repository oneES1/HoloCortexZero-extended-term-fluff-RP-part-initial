# 2026-05-16 adapter admission switches

## 结论

- QQ / OneBot：保留真实平台请求开关 `AUTO_ACCEPT_PRIVATE_REQUEST=true`、`AUTO_ACCEPT_GROUP_REQUEST=false`。
- Telegram：不新增群聊假开关。Telegram Bot API 没有“自动加入/接受群聊邀请”的适配器动作；`AUTO_ACCEPT_PRIVATE_CHAT` 文案已说明它只控制私聊 update 接入，群聊只能在 bot 被拉入后收到消息。
- Matrix：新增真实群聊邀请开关 `AUTO_JOIN_GROUP_INVITE=false`。私聊邀请和群聊邀请分别由 `AUTO_JOIN_PRIVATE_INVITE`、`AUTO_JOIN_GROUP_INVITE` 控制。

## 边界

适配器开关只管平台会话接入；是否回复仍由 HCZ 主干的 `DBChatChannel.is_active`、触发逻辑、高级 context 和 tool 链状态决定。

## 验证

- `python3 -m py_compile holo_cortex_zero/adapters/telegram/config.py holo_cortex_zero/adapters/matrix/config.py holo_cortex_zero/adapters/matrix/adapter.py` 通过。
- `rg "AUTO_ACCEPT_GROUP_CHAT|AUTO_JOIN_GROUP_CHAT" holo_cortex_zero/adapters/telegram docs frontend /path/to/runtime-data/configs/telegram/config.yaml` 无结果，确认 TG 未新增假群聊开关。
