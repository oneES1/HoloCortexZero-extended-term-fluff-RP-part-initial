# 2026-05-20 Docker 日志轮转与依赖健康检查

## 背景

Docker root 重建后继续审查运行态，确认 `/var/lib/docker` 已恢复到由活跃镜像主导的正常体积，但发现两个运维缺口：

- 所有容器使用 `json-file` 日志驱动且 `LogConfig.Config` 为空，没有 `max-size` / `max-file` 限制。
- `hcz_postgres`、`hcz_qdrant`、`hcz_napcat` 没有 Docker healthcheck，Docker 只能知道容器进程是否存活，不能判断服务是否可用。

## 修改

- `/etc/docker/daemon.json` 增加 Docker daemon 级日志轮转：
  - `log-driver=json-file`
  - `max-size=20m`
  - `max-file=3`
- `docker-compose.yml` 为 HCZ 依赖服务增加健康检查：
  - `hcz_postgres`: `pg_isready -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"`
  - `hcz_qdrant`: 使用 bash `/dev/tcp` 请求 `127.0.0.1:6333/healthz` 并匹配 `200 OK`
  - `hcz_napcat`: 使用容器内已有 `curl` 请求 `127.0.0.1:$${NAPCAT_WEBUI_PORT:-65535}/`
- `holo_cortex_zero` 对 `hcz_postgres` / `hcz_qdrant` 的 `depends_on` 从 `service_started` 收紧为 `service_healthy`。

## 约束

- 不给镜像新增包。
- 不读取大日志内容，只检查日志文件大小和 Docker 元数据。
- 不改业务逻辑。
- 宿主 Docker daemon 配置不在 git 仓库内，只能在服务器本机验证。

## 验证点

- `dockerd --validate --config-file=/etc/docker/daemon.json` 必须返回 `configuration OK`。
- `docker compose -f docker-compose.yml config` 必须能渲染 healthcheck。
- recreate 后检查：
  - `holo_cortex_zero` healthy
  - `hcz_postgres` healthy
  - `hcz_qdrant` healthy
  - `hcz_napcat` healthy
  - 新容器 `LogConfig.Config` 包含 `max-size:20m` 与 `max-file:3`

## 风险与回滚

- 重启 Docker daemon 与 recreate 容器会短暂中断本机 HCZ / Matrix 服务。
- `/etc/docker/daemon.json` 已在修改前备份为 `/etc/docker/daemon.json.bak-20260520-212003`。
- `docker-compose.yml` 已在修改前临时备份为 `/home/ubuntu/hcz-deploy/docker-compose.yml.bak-20260520-212003`，验证后不提交该备份文件。
