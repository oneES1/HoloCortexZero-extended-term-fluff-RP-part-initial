# 2026-04-10 sing-box hk003/hk004 自动切换

## 背景

- `HCZ` 运行时模型代理统一走 `socks5h://<CONTAINER_SOCKS_PROXY>`
- 该入口由宿主机 `<PROXY_SERVICE_NAME>` 提供
- 2026-04-10 13:35 左右，业务侧出现 `RemoteProtocolError` 与 `ProxyError(Connection refused)`
- 进一步排查发现，真正故障点是 `<PROXY_SERVICE_NAME>` 的上游节点 `<PROXY_UPSTREAM_HOST_PRIMARY>:<PROXY_UPSTREAM_PORT_PRIMARY>`

## 定点探测

- 目标：在不改 HCZ 主链逻辑的前提下，为 `<PROXY_SOCKS_PORT>` 增加备用节点 `hk004`
- 采用与现有 `hk003` 相同密码，逐端口临时起 `sing-box` 探测
- 结果：
  - `<PROXY_UPSTREAM_HOST_SECONDARY>:<PROXY_UPSTREAM_PORT_SECONDARY>`
  - `tls.server_name = <PROXY_UPSTREAM_TLS_SERVER_NAME_SECONDARY>`
  - 可通过该节点成功代理访问 `https://api.uniapi.io/v1/models`，返回 `401`

## 修改

- 修改文件：`/path/to/sing-box/config-primary.json`
- 主干保持不变：继续暴露同一个 `SOCKS` 入口 `<LOCAL_SOCKS_PROXY>` / `<CONTAINER_SOCKS_PROXY>`
- 将原单一出站 `proxy` 改为：
  - `hk003`：原有主节点
  - `hk004`：新增备用节点
  - `proxy`：`urltest` 组，负责在 `hk003` / `hk004` 间自动选择

## 验证

- `sing-box check -c /path/to/sing-box/config-primary.json` 通过
- 重启 `<PROXY_SERVICE_NAME>` 后：
  - 宿主机通过 `<LOCAL_SOCKS_PROXY>` 可访问 UniAPI
  - 容器通过 `<CONTAINER_SOCKS_PROXY>` 可访问 UniAPI
- 由于 `hk003` 可能瞬时恢复，`urltest` 实际选中哪条节点取决于运行时连通性与时延

## 风险与回滚

- 风险：`urltest` 为自动选择，短时抖动时可能在两条节点之间切换
- 风险：备用节点参数目前通过在线探测确认，可用但并非来自本地静态配置文件
- 回滚：恢复 `/path/to/sing-box/config-primary.json.bak-TIMESTAMP-secondary` 并重启 `<PROXY_SERVICE_NAME>`

## 2026-04-10 追加调优

- 根据运行需求，将 `urltest.interval` 从 `3m` 调整为 `1m`
- 将 `urltest.tolerance` 从 `100` 调整为 `500`
- 目的：更快感知主节点故障，同时减少因小幅延迟波动造成的来回切换
