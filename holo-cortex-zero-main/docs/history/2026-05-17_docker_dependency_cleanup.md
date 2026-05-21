# Docker Dependency Cleanup

## 背景

开源友好审查发现运行镜像安装了 `docker.io`，同时 Python 依赖包含 `docker` SDK。复查运行时代码后，主链路没有调用容器内 `docker` CLI，也没有导入 `docker` SDK。

当前仍使用 Docker Engine API 的功能包括：

- WebUI 重启当前容器。
- OneBot/NapCat 容器状态与日志读取。

这些功能通过 `aiodocker` 连接 `/var/run/docker.sock` 实现，不依赖镜像内安装 Docker CLI/daemon。

## 变更

- 删除 Dockerfile 中的 `apt install -y docker.io`。
- 删除重复的 `apt install -y git`。
- 删除未使用的 Python 依赖 `docker>=7.1.0,<8.0.0`。
- 保留 `aiodocker` 依赖。

## 影响

- 减少镜像体积与容器内 Docker CLI/daemon 权限预期。
- 不影响通过 Docker socket 使用 `aiodocker` 管理自身容器和 NapCat 容器。
- 不变更 compose 挂载与运行拓扑。

## 验证

- `rg` 确认非文档运行时代码没有 `import docker`、`from docker` 或容器内 `docker` CLI 调用。
- `uv run python -m compileall holo_cortex_zero/tools/docker_util.py holo_cortex_zero/adapters/onebot_v11/routers.py holo_cortex_zero/routers/restart.py`
- `uv sync --frozen --no-dev --dry-run`
