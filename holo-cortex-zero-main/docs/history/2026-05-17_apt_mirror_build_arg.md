# Build Mirror Args

## 背景

Docker build 重新执行 apt 层时，`deb.debian.org` 经 SOCKS 代理出现间歇 `general SOCKS server failure`。这属于构建网络出口问题，不是 Python SOCKS 依赖缺失。

前端构建原本固定使用 `https://registry.npmmirror.com`，国内友好但不适合海外、企业内网、私有 npm registry 等开源部署场景。

## 变更

- Dockerfile 新增可选 apt build args：
  - `APT_DEBIAN_MIRROR`
  - `APT_SECURITY_MIRROR`
  - `APT_NO_PROXY`
- Dockerfile 新增可选 npm build arg：
  - `NPM_REGISTRY`
- 默认不改 Debian 官方源和 npm 官方默认源，保持开源默认中立。
- 根 compose 将 `HCZ_APT_*` / `HCZ_NPM_REGISTRY` 变量透传给 build args。
- 当前部署 `.env` 可配置腾讯云 Debian 镜像、npm 镜像，并对 apt 禁用代理。

## 影响

- 开源第三方可按自身网络选择 apt 镜像源。
- 开源第三方可按自身网络选择 npm registry。
- 当前腾讯云构建不再强制通过 SOCKS 访问 `deb.debian.org`。
- Dockerfile 不再强制所有部署者使用 npmmirror。
- 不改变运行时代理配置；仅影响 Docker build 阶段 apt。

## 验证

- `docker compose -f docker-compose.yml build holo_cortex_zero`
