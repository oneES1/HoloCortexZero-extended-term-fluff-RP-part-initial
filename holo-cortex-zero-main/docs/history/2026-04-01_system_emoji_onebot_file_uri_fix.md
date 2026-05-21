# 2026-04-01 system_emoji OneBot 本地图片 URI 热修

## 现象

- `system_emoji` 在 OneBot 群聊发送图片时失败
- 运行日志出现：`文件处理失败: 识别URL失败, uri=<CONTAINER_DATA_DIR>/system/emoji/*.png`
- 文本已发出，但图片资源补发失败并回退纯文本

## 根因

- `system_emoji` 按主干约定通过 `PlatformSendSegment(type=image, file_path=...)` 发送本地图片
- `OnebotV11Adapter` 将本地图片路径转换到协议端可访问路径后，直接把裸绝对路径传给 `MessageSegment.image(file=...)`
- NapCat 将该字段按 URI 解析，裸路径 `<CONTAINER_DATA_DIR>/...` 不带 scheme，被判定为非法 URL

## 修复

- 仅修改 `holo_cortex_zero/adapters/onebot_v11/adapter.py`
- 保留现有挂载路径转换主干
- 在图片富文本发送出口把本地路径标准化为 `file:///...` URI 后再交给 OneBot
- 补充一条发送日志，记录原始路径与规范化 URI，便于后续排查
- 不改 `system_emoji` 业务逻辑，不改 `FILE` 上传链路，不改语音链路

## 验证

- `python3 - <<'PY'` 方式对 `adapter.py` 做内存编译校验
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`
- 在 QQ/TG 触发 `system_emoji` 发送，确认不再出现 `识别URL失败`
- 观察日志应出现 `OneBot 图片本地路径已规范为 file URI`

## 回滚点

- 本次热修应独立提交，可按提交哈希单独回退
