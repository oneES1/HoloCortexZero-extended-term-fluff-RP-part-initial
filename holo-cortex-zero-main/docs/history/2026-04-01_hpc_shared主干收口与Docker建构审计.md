# 2026-04-01 hpc_shared 主干收口与 Docker 建构审计

## 结论
- `hpc_shared` 唯一宿主实盘路径固定为 `/path/to<CONTAINER_WORKSPACE_DIR>/hpc_shared`
- `HCZ_DATA_DIR` 下的 `hpc_shared` 属于误导影子目录，已从 compose / 入口脚本 / 默认配置主干中移除
- NapCat 与主服务统一通过 `<CONTAINER_WORKSPACE_DIR>` 访问共享文件，不再依赖 `<CONTAINER_DATA_DIR>/hpc_shared`

## 代码与配置收口
- `holo_cortex_zero/core/config.py` 与 `holo_cortex_zero/services/file_system/service.py` 的高级文件根默认值已切到 `OsEnv.WORKSPACE_ROOT / "hpc_shared"`
- `holo_cortex_zero/adapters/onebot_v11/adapter.py` 的协议端路径换算已支持两类主干：
  - `DATA_DIR` 里的运行态文件 -> 固定映射到协议端 `<CONTAINER_DATA_DIR>`
  - 工作区里的文件 -> 固定映射到协议端 `<CONTAINER_WORKSPACE_DIR>`
- `docker-compose.yml` 与 `docker/docker-compose.dev.yml` 已同步去掉 `<CONTAINER_DATA_DIR>/hpc_shared` / `<CONTAINER_WORKSPACE_DIR>/hpc_shared` 挂载别名
- 误导性的备用部署模板 `docker/docker-compose.yml`、`docker/docker-compose-x-napcat.yml` 已删除
- 根目录热更新 compose 已直接使用工作区 `frontend/dist`，不再依赖 `HCZ_DATA_DIR/static` 旧静态目录

## 审计结果
- Docker 初始化权限修复只保留真实运行态目录和工作区 `hpc_shared`
- `HCZ/configs/` 外层占位配置不再保留，避免与运行态 `HCZ_DATA_DIR/configs/` 混淆
- 根目录 `Dockerfile.holo_cortex_zero` 已删除，避免与 `holo-cortex-zero-main/dockerfile` 双主干并存

## 仍然保留
- `docker.sock` 挂载保留
- 根目录 `docker-compose.yml` 保留，作为唯一部署入口
- `holo-cortex-zero-main/docker/docker-compose.dev.yml` 保留，作为开发环境入口
