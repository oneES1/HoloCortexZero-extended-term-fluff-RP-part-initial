# 2026-04-10 UniAPI 代理失效诊断

## 背景

- 线上主模型组 `Uni-qwen-3.5-plus` 报：`RemoteProtocolError('Server disconnected without sending a response.')`
- 同一时刻 fallback 模型组 `Uni-qwen397` 报：`ProxyError('Proxy Server could not connect: Connection refused.')`
- 两条链路都走系统设置 `DEFAULT_PROXY=socks5h://<CONTAINER_SOCKS_PROXY>`

## 先排除的误判

- 曾短暂尝试把 `DEFAULT_PROXY` 切到 `http://<LOCAL_HTTP_PROXY>`
- 随后容器内验证发现该地址仅宿主机 `code-server` 可达，容器内不可达
- 该改动已回滚，运行时已恢复原始 `SOCKS` 代理配置

## 定点结论

### 1. 业务代码主链本身没有稳定复现问题

- 在 `holo_cortex_zero` 容器内，使用应用同版本 `httpx 0.27.2`
- 直接对 `https://api.uniapi.io/v1/chat/completions` 发送原始请求载荷，多次返回 `200`
- 通过 `socks5://<CONTAINER_SOCKS_PROXY>` 发送同一原始请求载荷，多次返回 `200`
- 并发 12 路 `SOCKS` 请求，同样全部成功

### 2. 问题出在 `sing-box-hk003` 的上游出站节点瞬时故障

- `<CONTAINER_SOCKS_PROXY>` 对应宿主机 `<PROXY_SERVICE_NAME>`
- 其出站为 Trojan 节点：`<PROXY_UPSTREAM_HOST_PRIMARY>:<PROXY_UPSTREAM_PORT_PRIMARY>`
- 在告警发生的同一分钟，系统日志出现了与业务时间点严格对齐的代理错误：
  - `13:35:27`：对 `api.uniapi.io:443` 的代理出站报 `dial tcp <PROXY_UPSTREAM_IP_PRIMARY>:<PROXY_UPSTREAM_PORT_PRIMARY>: connect: connection refused`
  - 同时段还存在 `read: connection reset by peer`

### 3. 为什么业务层会表现成两个不同异常

- 主请求已经进入上游链路后被异常断开，于是 `httpx/httpcore` 在应用层看到的是 `RemoteProtocolError`
- fallback 随后新建连接时，`sing-box` 到其上游代理节点直接被拒绝，于是应用层拿到 `ProxyError(Connection refused)`
- 因此这不是 `qwen3.5-plus` 协议问题，也不是 HCZ 的 `chat.completions` 主干实现错误，而是代理出口在那一瞬间不稳定

## 证据位点

- 业务告警：`/path/to/runtime-data/logs/app/app.log`
- 代理服务：`<PROXY_SERVICE_NAME>`
- 代理配置：`/path/to/sing-box/config-primary.json`
- HCZ 运行时配置：`/path/to/runtime-data/configs/holo-cortex-zero.yaml`

## 当前状态

- `DEFAULT_PROXY` 已恢复为 `socks5h://<CONTAINER_SOCKS_PROXY>`
- `holo_cortex_zero` 容器已最小重建并恢复健康
- 目前未保留任何错误的 `HTTP` 代理切换配置

## 后续建议

- 若要“继续走代理且更稳”，优先处理代理出口，而不是改 HCZ 主链：
  - 给 `<PROXY_SERVICE_NAME>` 增加备用出站/自动切换
  - 或把 HCZ 的模型代理切到更稳定的代理入口
  - 或至少对 `<PROXY_SERVICE_NAME>` 增加健康探测与失败告警
- 若你要我继续，我下一步建议做：
  - 方案 A：为 `<PROXY_SOCKS_PORT>` 增加第二个稳定出站并做自动切换
  - 方案 B：只给 HCZ 模型单独配一条容器可达且更稳的代理入口
