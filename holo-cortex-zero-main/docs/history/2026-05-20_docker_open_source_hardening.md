# Docker 开源部署硬化

## 背景

开源部署复审确认：固定 OneBot token 与 `541955254` persona seed 是有意设计，不作为开源阻断项。真正风险集中在默认密码、第三方镜像可复现性、release 打包无效 I/O 和安装提示错误。

## 证据

- 当前 Docker 运行态健康：`hcz_postgres`、`hcz_qdrant`、`hcz_napcat`、`holo_cortex_zero` 均已有 healthcheck。
- `frontend/node_modules` 约 1.1G，旧 release 脚本会先 rsync 再删除，造成打包阶段无效磁盘 I/O。
- `.env.share.example` 保留 `change_me_*` 提示值；如果用户手动复制后不改，旧流程不会机械阻断。
- 当前本机 `.env` 的 `POSTGRES_PASSWORD` 是公开弱默认，需要迁移。
- 旧安装脚本提示 `docker logs ... napcat`，但 compose 容器名是 `hcz_napcat`。

## 修复

- 安装脚本在 `POSTGRES_PASSWORD` 为空、`change_me_*`、`holo_cortex_zero` 时生成 32 位随机值。
- 安装脚本在 `HCZ_ADMIN_PASSWORD` 为空、`change_me_*`、`123456` 时生成 32 位随机值。
- PostgreSQL 与主服务入口脚本拒绝空值、占位值和公开弱默认密码。
- 本机 PostgreSQL 用户密码已迁移为随机强密码，并同步写入 `.env`。
- 主 compose 与 dev compose 固定 PostgreSQL、Qdrant、NapCat 镜像 digest。
- dev compose 删除 `POSTGRES_HOST_AUTH_METHOD=trust`，数据库与 Qdrant 端口只绑定 `127.0.0.1`。
- release 脚本在 rsync 阶段排除 `frontend/node_modules`、开发 i18n 修复脚本、验证脚本和 dev compose。
- 安装脚本日志提示改为 `hcz_napcat`。

## 验证

执行时需要验证：

```bash
bash -n make_docker_release_bundle.sh
bash -n holo-cortex-zero-main/scripts/hcz_runtime_entrypoint.sh
bash -n holo-cortex-zero-main/scripts/hcz_postgres_entrypoint.sh
bash -n holo-cortex-zero-main/docker/install.sh
bash -n holo-cortex-zero-main/docker/install_i18n.sh
docker compose --env-file .env.share.example -f docker-compose.yml config >/tmp/hcz-open-fixed.yml
OUT_DIR=/tmp/hcz_release_fixed STAMP=fixed ./make_docker_release_bundle.sh
docker compose -f docker-compose.yml ps
curl -fsS http://127.0.0.1:20261/api/health
```
