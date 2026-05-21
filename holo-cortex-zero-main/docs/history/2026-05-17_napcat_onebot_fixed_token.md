# 2026-05-17 NapCat OneBot 固定 Token 收口

## 背景

NapCat 反向 WebSocket 当前使用 `/path/to/runtime-data/napcat_data/napcat/onebot11_<ONEBOT_SELF_ID>.json`：

- `websocketClients` 数量：1
- `url`：`ws://holo_cortex_zero:20261/onebot/v11/ws`
- `token`：`<ONEBOT_ACCESS_TOKEN>`

HCZ 运行态原先只向容器传入 `ONEBOT_ACCESS_TOKEN`，且 `/path/to/deploy-root/.env` 中该值为空。NoneBot OneBot v11 适配器实际读取 `ONEBOT_V11_ACCESS_TOKEN`（配置别名 `onebot_v11_access_token`）并用它校验 WebSocket `Authorization`。

这导致 NapCat JSON、安装脚本随机值、NoneBot 真校验变量存在三处来源，新手部署时容易配置断裂。

## 修改

1. `docker-compose.yml`
   - `holo_cortex_zero` 同时传入：
     - `ONEBOT_ACCESS_TOKEN=${ONEBOT_ACCESS_TOKEN:-<ONEBOT_ACCESS_TOKEN>}`
     - `ONEBOT_V11_ACCESS_TOKEN=${ONEBOT_ACCESS_TOKEN:-<ONEBOT_ACCESS_TOKEN>}`
   - `hcz_napcat` 传入同一个 `ONEBOT_ACCESS_TOKEN`。

2. `scripts/hcz_napcat_entrypoint.sh`
   - 启动前强制写入 OneBot v11 主干配置。
   - 主干固定为 `ws://holo_cortex_zero:20261/onebot/v11/ws`。
   - token 固定为 `<ONEBOT_ACCESS_TOKEN>`。
   - 仅保留 HCZ 一体化部署主干，不维护 NapCat WebUI 手动 token 与安装脚本随机 token 的并行来源。

3. 安装脚本
   - `docker/install.sh`
   - `docker/install_i18n.sh`
   - `docker/wrtinstall.sh`
   - 删除 OneBot token 随机生成逻辑，空值时写入固定默认 token。

4. 示例配置
   - `.env.example`
   - `docker/.env.example`
   - 默认写入固定 token。

5. 当前部署运行态
   - `/path/to/deploy-root/.env` 已写入固定 token。

## 验证计划

- `bash -n` 验证改动脚本语法。
- `docker compose config` 验证 compose 展开。
- `docker compose up -d --no-deps --force-recreate holo_cortex_zero hcz_napcat` 同步运行态。
- `docker inspect` 验证 HCZ 与 NapCat 环境变量。
- 读取 NapCat 持久化 JSON 验证 URL 与 token。
- 最后由用户在 QQ 或 TG 发送真实消息验证。

## 风险与回滚

风险：外部手动接入同一 NapCat OneBot 配置的非 HCZ 客户端会被固定主干覆盖。当前部署证据显示 `websocketClients` 数量为 1，目标就是 HCZ 容器服务，风险可接受。

回滚点：本次 git 提交；运行态 `.env` 可将 `ONEBOT_ACCESS_TOKEN` 改回空值或旧值后重建 `holo_cortex_zero` 与 `hcz_napcat`。
