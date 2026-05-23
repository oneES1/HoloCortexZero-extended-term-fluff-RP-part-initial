# 2026-05-17 国内构建配置固化

## 背景

普通 `docker compose up --no-deps --build --force-recreate holo_cortex_zero` 在国内网络下容易卡在依赖下载阶段。此前一次成功构建使用了手工 `docker build --network=host` 和临时 build proxy，但该路径没有进入正式 compose / install 主干。

## 修正

- `docker-compose.yml` 增加 build-only `HCZ_BUILD_NETWORK` 和 `HCZ_BUILD_*_PROXY` 入口。
- `.env.share.example` 与 `docker/.env.example` 补全 build-only 构建网络、代理与 `HCZ_UV_DEFAULT_INDEX`。
- `docker/install.sh` 支持 `cn` / `--cn`，显式选择国内构建源时写入 npm、uv、apt 国内源。
- 部署文档明确这些变量只属于 Docker build，不属于 HCZ 业务运行代理、模型 API URL 或工具联网配置。
- 部署文档补充默认语义：正常部署走官方源；传入 `cn` 才进入国内构建 profile。

## 边界

- 不新增业务代理兜底。
- 不把代理注入运行态容器环境。
- 不改变模型组、Tavily、Telegram、Matrix 等业务网络配置来源。
