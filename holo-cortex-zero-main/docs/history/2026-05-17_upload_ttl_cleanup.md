# 2026-05-17 uploads TTL cleanup

## 背景

- 目标：避免 `uploads` 长期堆积占用服务器磁盘，同时保持开源第三方 Docker 部署路径友好。
- 当前运行态容器内 `HCZ_DATA_DIR=<CONTAINER_DATA_DIR>`，`USER_UPLOAD_DIR=OsEnv.DATA_DIR + "/uploads"`，实际清理目标为 `<CONTAINER_DATA_DIR>/uploads`。
- 宿主挂载为 `${HCZ_DATA_DIR}/uploads:<CONTAINER_DATA_DIR>/uploads:rw`，不在代码中写死宿主路径。

## 修改前证据

- `/path/to/runtime-data/uploads`: `1.6G`
- `uploads` 文件数：`5403`
- 超过 6 小时文件数：`5403`
- 6 小时内文件数：`0`
- `/path/to/runtime-data/quarantine_uploads`: `96M`

## 实现

- 新增 `holo_cortex_zero/services/file_system/upload_cleanup.py`。
- 在应用启动时启动 `upload_cleanup_service`，关闭时停止。
- 默认配置：
  - `HCZ_UPLOAD_CLEANUP_ENABLED=true`
  - `HCZ_UPLOAD_CLEANUP_TTL_SECONDS=21600`
  - `HCZ_UPLOAD_CLEANUP_INTERVAL_SECONDS=21600`
  - `HCZ_UPLOAD_CLEANUP_STARTUP_DELAY_SECONDS=5`
- 清理规则：
  - 只处理 `USER_UPLOAD_DIR`。
  - 只删除 `mtime <= now - ttl_seconds` 的普通文件。
  - 跳过 symlink。
  - 清理后删除空子目录。
  - 保留 uploads 根目录。
  - 输出聚合日志：root、TTL、interval、删除文件数、删除目录数、删除字节数、失败数、耗时。

## 边界

- 不改附件入库主干。
- 不迁移 `uploads` 到 `quarantine_uploads`。
- 不清理 `quarantine_uploads`、`logs`、`configs`、`system`、`tool_state`、`backups`、`napcat_data`、Postgres、Qdrant、`hpc_shared`、`draw`。
- 不使用 shell `rm -rf`。
- 不写死 `/path/to/runtime-data`。

## 行为影响

- 超过 TTL 的历史本地媒体文件会被删除。
- 数据库中的文本消息不受影响。
- 历史消息若引用已删除的本地媒体文件，上下文回放会找不到该媒体并跳过。
- 最近 TTL 窗口内的新上传文件不会被删除。

## 验证

- `python -m compileall holo_cortex_zero/services/file_system/upload_cleanup.py holo_cortex_zero/__init__.py`
- `HCZ_UPLOAD_CLEANUP_TTL_SECONDS=21600 python - <<'PY' ... upload_cleanup_service.cleanup_once() ... PY`
- 容器内确认：
  - `docker exec holo_cortex_zero sh -lc 'printf "DATA_DIR=%s\n" "$HCZ_DATA_DIR"; du -sh <CONTAINER_DATA_DIR>/uploads; find <CONTAINER_DATA_DIR>/uploads -type f | wc -l'`

## 部署

只重建后端本体容器，不触碰依赖服务：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

## 回滚点

- 快照提交：`2f7c54a backup(runtime): snapshot before upload cleanup`
- 功能提交：待提交
