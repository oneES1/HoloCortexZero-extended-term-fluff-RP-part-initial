# 2026-05-16 OneBot CQ code removal

## 结论

OneBot CQ 文本旁路已删除。HCZ 出站只保留主干标准消息段，再由 OneBot 适配器转换为 NoneBot `MessageSegment`：

- text -> `MessageSegment.text`
- at -> `MessageSegment.at`
- image -> `MessageSegment.image`
- voice -> `MessageSegment.record`
- file -> OneBot file upload API

## 删除内容

- 删除 `OnebotV11Config.RESOLVE_CQ_CODE`。
- 删除 OneBot `send_group_msg` / `send_private_msg` 的 `auto_escape` 配置入口。
- 删除 `ChatMessage.raw_cq_code`。
- 删除 `DBChatMessage.raw_cq_code` ORM 字段。
- 删除所有 `ChatMessage(...)` 构造点的 `raw_cq_code` 参数。
- 删除运行配置 `/path/to/runtime-data/configs/onebot_v11/config.yaml` 中的 `RESOLVE_CQ_CODE`。
- 删除 PostgreSQL `chat_message.raw_cq_code` 列。

## 数据库证据

删除列前确认：

```text
SELECT COUNT(*) AS rows_with_raw_cq FROM chat_message
WHERE raw_cq_code IS NOT NULL AND raw_cq_code <> '';

rows_with_raw_cq = 0
```

删除列后确认：

```text
SELECT column_name FROM information_schema.columns
WHERE table_name='chat_message' AND column_name='raw_cq_code';

0 rows
```

## 验证

- `rg "RESOLVE_CQ_CODE|raw_cq_code|CQ 码|CQ码|\[CQ:|auto_escape" holo_cortex_zero docs frontend /path/to/runtime-data/configs` 无结果。
- `python3 -m py_compile` 覆盖 OneBot、collector、ChatMessage、DBChatMessage、message_service、系统触发构造点。
- 后端容器重建后状态：`running healthy`。
