# 2026-05-17 build Python index config

## 背景

开源部署构建配置已经区分了运行时业务网络配置与构建期镜像源配置：

- 业务运行时代理、模型 API URL 只允许来自 `/path/to/runtime-data/configs/*`。
- Docker `.env` 不承载业务代理、API URL、Docker gateway 兜底。
- 构建期可以使用国内源以提升第三方部署成功率，但这些配置只传入 `docker build`。

本次复查发现 apt 与 npm/pnpm 已有构建期国内源开关，但 Python 依赖安装的 `uv sync --frozen --no-dev` 仍使用默认 PyPI，实际重建时长时间重复下载 wheel。

## 修改

- 新增 Compose build arg `UV_DEFAULT_INDEX: ${HCZ_UV_DEFAULT_INDEX:-}`。
- 新增示例配置 `HCZ_UV_DEFAULT_INDEX=`。
- 当前生产 `.env` 设置为一个国内 PyPI 镜像；该值不提交进仓库。
- Dockerfile 在 `uv sync` 时仅在 build arg 非空时追加 `--default-index`。

## 边界

- `HCZ_UV_DEFAULT_INDEX` 只用于 `docker build`。
- 不写入容器运行时 environment。
- 不影响框架业务请求、LLM API、Telegram/Matrix 代理、Tavily 或工具 HTTP 请求。
- 不增加业务代理兜底，不读取宿主 `HTTP_PROXY` / `ALL_PROXY`。
