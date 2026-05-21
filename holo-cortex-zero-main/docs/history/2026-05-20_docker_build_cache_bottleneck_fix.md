# Docker build cache bottleneck fix

## 背景

2026-05-20 审查 `holo_cortex_zero` Docker 重建耗时问题。

只做只读探测与安全清理，未读取大日志，未重启家庭服务器，未触碰 frp。

## 复现事实

- `/home/ubuntu/hcz-deploy/holo-cortex-zero-main` 构建上下文目录总量：`1.5G`
- `frontend/node_modules`：`1.1G`
- `.venv`：`376M`
- 当前镜像 `holo-cortex-zero-with-ffprobe:local`：`1.04GB`
- `docker history` 大层：
  - `apt install libmagic-dev libolm-dev ffmpeg`：`481MB`
  - `uv sync --frozen --no-dev`：`340MB`
  - `COPY /uv /uvx`：`57.4MB`
- 清理前：
  - Docker images reclaimable：`1.391GB`
  - Docker build cache reclaimable：`10.86GB`
- 清理后：
  - Docker images reclaimable：`127.3MB`
  - Docker build cache：`0B`
  - `docker builder prune -f` 实际释放：`11.55GB`

## 根因

1. `.dockerignore` 未排除 `frontend/node_modules/`，导致本地 `1.1G` 前端依赖进入 Docker build context 扫描/发送范围。
2. Dockerfile 在 `uv sync --frozen --no-dev` 前复制了 `holo_cortex_zero/` 和 `tool_runtime/`，普通业务源码变更会打穿 Python 第三方依赖缓存层。

## 修改

1. `.dockerignore` 增加 `frontend/node_modules/`。
2. Dockerfile 拆分 Python 依赖同步：
   - 源码复制前执行 `uv sync --frozen --no-dev --no-install-project`，缓存第三方依赖。
   - 源码复制后保留 `uv sync --frozen --no-dev`，安装当前项目包。

## 影响

- 业务源码变更后，第三方 Python 依赖层不应再因 `COPY holo_cortex_zero` / `COPY tool_runtime` 失效。
- 前端本地依赖不再进入 build context。
- 第一次重新 build 因刚清理过 builder cache，仍会完整下载/安装依赖；第二次同类后端源码变更才体现缓存收益。

## 回滚点

- 回滚 `.dockerignore` 中 `frontend/node_modules/`。
- 回滚 Dockerfile 中新增的 `uv sync --no-install-project` 层，并恢复为源码复制后单次 `uv sync --frozen --no-dev`。
