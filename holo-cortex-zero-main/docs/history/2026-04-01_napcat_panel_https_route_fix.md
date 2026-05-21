# 2026-04-01 NapCat 面板 HTTPS 单地址代理修复

## 问题
- 宿主 `443` 统一反代到 HCZ，NapCat 仅监听 `<LEGACY_LOOPBACK_HOST>:<LEGACY_NAPCAT_WEBUI_PORT>`
- HCZ 内配置的 `NAPCAT_ACCESS_URL` 仍指向 `http://<LEGACY_LOOPBACK_HOST>:<LEGACY_NAPCAT_WEBUI_PORT>/webui`
- 远端设备通过苹果私签直接访问 `https://<PUBLIC_SERVER_IP>`，无法使用额外子域名作为稳定入口
- NapCat WebUI 前端把根路径资源写死为 `/webui/`、`/api`、`/files/`，直接挂到 HCZ 同域子路径会与 HCZ 自身 `/webui`、`/api` 冲突

## 最小修复
- 统一保留单地址入口 `https://<PUBLIC_SERVER_IP>`
- 新增兼容代理前缀：NapCat 外部访问地址改为 `/napcat/webui/`
- 宿主 `nginx` 在 `/napcat/webui/`、`/napcat/api/`、`/napcat/files/` 上反代到 `<LEGACY_LOOPBACK_HOST>:<LEGACY_NAPCAT_WEBUI_PORT>`
- 在反代层使用 `sub_filter` 对 NapCat 返回内容做主干级路径重写：
  - `/webui/` -> `/napcat/webui/`
  - `/api` -> `/napcat/api`
  - `/files/` -> `/napcat/files/`
- 对少量根路径登录入口保留精确代理：`/qq_login`、`/web_login`
- 将 `NAPCAT_ACCESS_URL` 改为 `https://<PUBLIC_SERVER_IP>/napcat/webui/`
- 只重载宿主 `nginx`，并最小重建 `holo_cortex_zero`

## 变更点
- 宿主反代：`/path/to/nginx-sites/<LEGACY_PANEL_CONF>`
- 运行配置：`/path/to/runtime-data/configs/onebot_v11/config.yaml`

## 验证
- `nginx -t`
- `curl -kI --resolve <PUBLIC_SERVER_IP>:443:<LEGACY_LOOPBACK_HOST> https://<PUBLIC_SERVER_IP>/napcat/webui/`
- `curl -ks --resolve <PUBLIC_SERVER_IP>:443:<LEGACY_LOOPBACK_HOST> https://<PUBLIC_SERVER_IP>/napcat/webui/`
- `curl -kI --resolve <PUBLIC_SERVER_IP>:443:<LEGACY_LOOPBACK_HOST> https://<PUBLIC_SERVER_IP>/napcat/api/auth/check`
- `curl -kI --resolve <PUBLIC_SERVER_IP>:443:<LEGACY_LOOPBACK_HOST> https://<PUBLIC_SERVER_IP>/`
