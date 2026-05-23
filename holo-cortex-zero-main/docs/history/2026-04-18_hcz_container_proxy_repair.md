# 2026-04-18 HCZ 容器代理修复

## 背景

- `holo_cortex_zero` 运行容器在 `hcz_network` 上实际拿到的是 `<LEGACY_DOCKER_BRIDGE_SUBNET>`
- 宿主机 `sing-box` 运行代理仍固定监听 `<LOCAL_HTTP_PROXY>` 与 `<CONTAINER_SOCKS_PROXY>`
- 结果：容器内 `ALL_PROXY=socks5h://<CONTAINER_SOCKS_PROXY>` 指向失效地址，代理链路中断
- 同时，镜像内残留了构建期小写代理变量，运行时只覆盖了大写变量，造成大小写代理值不一致

## 定位

- `docker network inspect hcz_network` 显示网桥网关是 `<LEGACY_HOST_GATEWAY_IP>`
- `docker exec holo_cortex_zero` 内对 `<CONTAINER_SOCKS_PROXY>` / `<CONTAINER_HTTP_PROXY>` 均超时
- `docker exec holo_cortex_zero env | grep -i _proxy` 显示：
  - 大写变量走 `socks5h://<CONTAINER_SOCKS_PROXY>`
  - 小写变量残留 `<LOCAL_HTTP_PROXY>`，与运行态不一致

## 修改

- `docker-compose.yml`
- 为 `hcz_network` 固定 `ipam`：`<DOCKER_BRIDGE_SUBNET>`，网关 `<HOST_GATEWAY_IP>`
  - 为 `holo_cortex_zero` 运行环境补齐小写 `http_proxy` / `https_proxy` / `all_proxy` / `no_proxy`
- 不改业务代理主干，不为单链路写特化逻辑，只修正容器网络与运行态环境对齐

## 验证目标

- 容器默认网关恢复为 `<HOST_GATEWAY_IP>`
- 容器内 `HTTP_PROXY` / `http_proxy` 等大小写环境变量一致
- 容器内可建立到 `<CONTAINER_SOCKS_PROXY>` 的连接，并可经代理访问外部模型入口

## 风险与回滚

- 风险：需要重建 `hcz_network`，会短暂重启 HCZ 相关容器
- 风险：若宿主机已有其他服务占用目标 Docker 桥接子网，网络创建会失败
- 回滚：撤销本次 `docker-compose.yml` 变更并重建 Compose 网络
