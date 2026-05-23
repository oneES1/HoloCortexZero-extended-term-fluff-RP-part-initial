# Matrix 入站消息引用支持记录

## 背景

Element 的“回复消息”会在 `m.room.message.content` 中携带 Matrix 标准关系：

```text
m.relates_to.m.in_reply_to.event_id
```

Matrix adapter 原先只翻译 `m.text`、`m.image`、`m.audio`、`m.video`、`m.file`，没有把该关系转换为 HCZ 统一的
`ChatMessageSegmentReference`，因此 bot 只能看到当前消息正文，无法结构化知道用户引用了哪条消息。

## 修复原则

- 不新增 Matrix 专用引用主干。
- 只在 Matrix adapter 做协议翻译。
- 复用框架已有：
  - `ChatMessageSegmentReference`
  - `build_reference_segment`
  - `context_window._reference_segment_to_parts`
- DB 已有引用消息时复用原 `content_data`，包括已托管到 `hpc_shared` 的媒体 `local_path`。
- DB 未命中时只做 Matrix 事件文本/媒体摘要 fallback，不重复下载历史媒体，避免重复制造 `hpc_shared` 文件。

## 入站链路

1. Element 发送回复消息。
2. Matrix adapter 读取 `content["m.relates_to"]["m.in_reply_to"]["event_id"]`。
3. 优先按 `adapter_key=matrix`、`chat_key=matrix-private_<ADVANCED_USER_ID>`、`message_id=<event_id>` 查询 `chat_message`。
4. DB 命中：
   - `parse_content_data()` 复用原消息段。
   - 构造 `ChatMessageSegmentReference`。
   - 若原消息是图片/文件/音频/视频，引用段复用原 `local_path`，不重复下载。
5. DB 未命中：
   - 调 Matrix `/rooms/{room_id}/event/{event_id}` 拉原事件。
   - 只生成文本摘要：
     - `m.text` 使用正文。
     - `m.image` 使用 `[引用图片]`。
     - `m.audio` 使用 `[引用音频]`。
     - `m.video` 使用 `[引用视频]`。
     - `m.file` 使用 `[引用文件]`。
6. 当前消息正文剥离 Matrix fallback quote，只保留用户当前输入。
7. `PlatformMessage.ext_data` 写入 `ref_msg_id/ref_chat_key/ref_sender_id`。
8. `collect_message -> message_service -> context_window` 继续走统一主干。

## 验证

容器内 helper 验证：

```text
ref $abc
strip new
text new
ext {'ref_chat_key': 'matrix-private_<ADVANCED_USER_ID>', 'ref_msg_id': '$abc', 'ref_sender_id': '<ADVANCED_USER_ID>'}
```

预期用户实测日志：

```text
Matrix 引用解析成功: source=db room=!exampleRoom:example.com ref_event=... ref_db_id=... segments=...
Message Collect: [matrix-private_<ADVANCED_USER_ID>] matrix 海泡菜: 这句是什么意思 (ref: ...)
```

如果引用的是数据库未收录的历史消息，预期：

```text
Matrix 引用解析成功: source=matrix room=... ref_event=... segments=1
```

## 回滚

回滚本次提交后只重建后端容器：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```
