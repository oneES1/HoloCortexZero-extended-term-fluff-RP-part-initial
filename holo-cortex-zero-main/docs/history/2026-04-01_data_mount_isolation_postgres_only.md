# 2026-04-01 data 挂载收口：仅隔离 postgres_data / redis

## 目标
- 只把 `postgres_data` 与潜在 `redis` 数据从非 Postgres 容器视野里摘掉
- 不动 `hpc_shared` 主干
- 保留 bot / NapCat 必需运行路径

## 本次改动
- `holo_cortex_zero` 不再挂载整棵 `${HCZ_DATA_DIR}:<CONTAINER_DATA_DIR>`
- 改为精确挂载：`home`、`configs`、`logs`、`uploads`、`tool_state`、`system`、`quarantine_uploads`、`tmp`、`backups`、`napcat_data`
- `hcz_napcat` 不再挂载整棵 `${HCZ_DATA_DIR}:<CONTAINER_DATA_DIR>`
- 改为仅保留 `napcat_data` 相关挂载与现有 `QQ` / `napcat` 配置挂载
- `hcz_permissions_init` 不再看到整棵 `${HCZ_DATA_DIR}`，只修业务子目录，不再直接触碰 `postgres_data`
- PostgreSQL 权限仍只由 `hcz_postgres` 自己的 entrypoint 收口

## 影响判断
- `hpc_shared` 继续走 `<CONTAINER_WORKSPACE_DIR>/hpc_shared`，不受影响
- OneBot 文件出站仍可通过 `<CONTAINER_DATA_DIR>/napcat_data` 与 `<CONTAINER_WORKSPACE_DIR>` 主干访问
- 当前仓库中不存在实际 `redis` 服务/挂载，故本次对 `redis` 为结构预防性收口，不涉及现网迁移

## 验证要点
- 非 Postgres 容器 mount 列表中不再出现 `postgres_data`
- `GET /api/health` 正常
- `http://<LEGACY_LOOPBACK_HOST>:<LEGACY_NAPCAT_WEBUI_PORT>/webui/` 正常
- 两个容器内 `<CONTAINER_WORKSPACE_DIR>/hpc_shared` 仍存在
