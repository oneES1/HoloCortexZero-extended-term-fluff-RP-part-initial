# 2026-04-06 UniAPI Grok 地址切换联通性验证

## 背景
- 现象：`Uni-grok-4-1-fast` 原地址 `https://hk.uniapi.io/v1` 出现 `ConnectTimeout`。
- 对照：本机与 `hcz` 家庭工作站直连 `hk.uniapi.io:443` 都超时。
- 新地址候选：`https://api.uniapi.io/v1`。

## 本次最小变更
- 仅将运行时配置 `/path/to/runtime-data/configs/holo-cortex-zero.yaml` 中 `Uni-grok-4-1-fast` 的 `BASE_URL` 从 `https://hk.uniapi.io/v1` 切到 `https://api.uniapi.io/v1`。
- 未修改代码逻辑，未改动 fallback 组。
- 使用 `docker compose up -d --force-recreate holo_cortex_zero` 同步运行态，未触发镜像重建。

## 验证结果
- 容器健康检查恢复为 `healthy`。
- 容器内访问 `GET https://api.uniapi.io/v1` 返回 `HTTP/2 200`。
- 容器内访问 `POST https://api.uniapi.io/v1/responses`（无鉴权）返回 `HTTP/2 401`，说明新地址与接口路由可达。
- 容器内访问 `GET https://api.uniapi.io/v1/models`（使用当前 UniAPI token）返回 `HTTP/2 200`。
- 返回体中包含 `grok-4-1-fast-reasoning-latest`，说明当前 token 在新地址可见该模型。

## 结论
- 问题更像是 `hk.uniapi.io` 节点不可达，而不是本地代理整体故障。
- 对 `Uni-grok-4-1-fast` 切到 `https://api.uniapi.io/v1` 后，基础联通性与鉴权均正常。
- 后续若仍要彻底消除故障，需继续评估是否同步迁移其他仍指向 `hk.uniapi.io` 的模型组。
