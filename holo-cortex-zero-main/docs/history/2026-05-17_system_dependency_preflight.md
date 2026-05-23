# System Dependency Preflight

## 背景

源码部署用户缺少系统依赖时，过去可能在 import 阶段或功能触发时看到不直观的 traceback。Docker 部署会在镜像构建阶段安装这些依赖，但源码裸跑需要在宿主系统中提供。

## 变更

- 新增启动前系统依赖检查。
- 检查 `ffmpeg` 与 `ffprobe` 是否存在且可执行。
- 检查 `python-magic` 是否可实际调用 `magic.from_buffer`。
- 检查 Matrix E2EE 依赖 `nio.crypto` 与 `olm` 是否可导入。
- 缺失时打印明确 `logger.error`，然后抛出异常阻止服务启动。

## 影响

- 缺少关键系统依赖时服务会 fail fast，不再带病启动。
- Docker 部署不受影响，Dockerfile 已安装对应依赖。
- 源码裸跑用户需要按日志提示安装缺失系统包。

## 验证

- `uv run python -m compileall run_bot.py holo_cortex_zero/core/system_requirements.py`
- `uv run python - <<'PY' ... check_required_system_dependencies() ... PY`
