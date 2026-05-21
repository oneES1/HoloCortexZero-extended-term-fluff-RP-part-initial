# 2026-04-01 NapCat 反向 WS 宿主名残留修复

## 问题
- NapCat 运行态 OneBot 配置文件仍残留旧主机名 `<LEGACY_HCZ_SERVICE_NAME>`
- 当前 Docker 网络内实际主服务名为 `holo_cortex_zero`
- 导致 NapCat 反向连接 `ws://<LEGACY_HCZ_SERVICE_NAME>:20261/onebot/v11/ws` 时报 `ENOTFOUND <LEGACY_HCZ_SERVICE_NAME>`

## 根因
- 旧实例名残留在持久化运行态文件中，而不是代码主干配置中
- 当前生效文件：`/path/to/runtime-data/napcat_data/napcat/onebot11_<ONEBOT_SELF_ID>.json`
- 当前容器网络可解析服务名仅包含 `holo_cortex_zero`、`hcz_napcat`、`hcz_postgres`、`hcz_qdrant`

## 最小修复
- 备份运行态文件后，将反向 WS 地址从
  - `ws://<LEGACY_HCZ_SERVICE_NAME>:20261/onebot/v11/ws`
  改为
  - `ws://holo_cortex_zero:20261/onebot/v11/ws`
- 仅重建 `hcz_napcat`
- 不重建镜像，不动 HCZ 主服务，不触碰家庭服务器

## 验证
- 容器内配置文件已变更为 `ws://holo_cortex_zero:20261/onebot/v11/ws`
- 宿主机验证 `ws://<LEGACY_LOOPBACK_HOST>:20261/onebot/v11/ws` 在带 `X-Self-ID` 头时可成功完成 WebSocket 握手
- 重启后未再观察到 `ENOTFOUND <LEGACY_HCZ_SERVICE_NAME>`
- 本轮重启后 NapCat 日志出现一次 `Login Error, ErrType: 1 ErrCode: 3`，说明 QQ 侧登录态仍需继续观察/人工实测

## 变更点
- 运行态配置：`/path/to/runtime-data/napcat_data/napcat/onebot11_<ONEBOT_SELF_ID>.json`
- 备份文件：同目录下 `onebot11_<ONEBOT_SELF_ID>.json.bak-<timestamp>`
