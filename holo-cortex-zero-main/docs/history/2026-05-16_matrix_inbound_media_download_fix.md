# Matrix 入站图片下载修复记录

## 背景

Matrix 私聊房间 `!exampleRoom:example.com` 中，用户 `@owner:example.com`
发送图片后，HCZ bot 回复“看不到图片”。文字消息链路正常，问题限定在 Matrix 入站媒体下载。

## 证据

- Matrix adapter 日志显示下载失败：
  - `GET /_matrix/media/v3/download/example.com/byoGLEvbcUXeWkIhlWGZOdll -> HTTP 404`
- Synapse 数据库中该媒体存在：
  - `media_id = byoGLEvbcUXeWkIhlWGZOdll`
  - `media_type = image/jpeg`
  - `media_length = 110618`
  - `user_id = @owner:example.com`
- Synapse 容器磁盘中该媒体存在：
  - `/data/media_store/local_content/by/oG/LEvbcUXeWkIhlWGZOdll`
  - `110618 bytes`
- 同一媒体用 bot 凭据验证：
  - `/_matrix/media/v3/download/...` 返回 `404 application/json 45 bytes`
  - `/_matrix/client/v1/media/download/...` 返回 `200 image/jpeg 110618 bytes`

## 修复

只修改 Matrix 协议适配层的 `mxc://` 下载端点：

- 旧端点：`/_matrix/media/v3/download/{server_name}/{media_id}`
- 新端点：`/_matrix/client/v1/media/download/{server_name}/{media_id}`

不修改 HCZ 主消息链路，不修改高级文件系统，不新增 Matrix 专用落盘分支。

## 入站链路

1. Element 发送 `m.room.message`，`msgtype=m.image`，内容含 `mxc://...`。
2. Matrix adapter 在 `_build_message_segments` 中解析 `mxc://`。
3. `_download_mxc` 从 Synapse 下载媒体 bytes。
4. `resolve_incoming_attachment_mode` 按统一规则判断附件接收模式。
5. 当前 Matrix owner 被统一映射为高级用户 `<ADVANCED_USER_ID>`，私聊 `matrix-private_<ADVANCED_USER_ID>`，因此模式为：
   - `managed`
   - `reason=owner_private`
6. `ChatMessageSegmentImage.create_from_bytes(..., ingest_mode="managed")` 交给框架高级文件系统托管。
7. 运行态配置：
   - `ADVANCED_FILE_SYSTEM_ROOT: <CONTAINER_WORKSPACE_DIR>/hpc_shared`
   - 容器 `<CONTAINER_WORKSPACE_DIR>` 挂载宿主 `/path/to<CONTAINER_WORKSPACE_DIR>`
   - 因此实际宿主目录为 `/path/to<CONTAINER_WORKSPACE_DIR>/hpc_shared`
8. 消息进入 `collect_message`，写入 `chat_message.content_data`，后续上下文窗口解析 `ChatMessageSegmentImage.local_path` 并把图片作为多模态 part 交给模型。

## 回滚

回滚本次代码提交后，只重建后端容器：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```
