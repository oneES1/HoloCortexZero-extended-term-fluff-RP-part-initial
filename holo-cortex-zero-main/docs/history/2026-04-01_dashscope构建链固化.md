# 2026-04-01 dashscope 构建链固化

## 结论
- `dashscope` 已在 `pyproject.toml` 与 `uv.lock` 中声明并锁定
- 当前运行容器 `/app/.venv` 已可导入 `dashscope` 与 `dashscope.audio.tts_v2`
- 本次补充的是构建期代理固化，确保后续重建镜像时依赖拉取稳定

## 修改
- `docker-compose.yml`
  - 为 `holo_cortex_zero` 的 `build.args` 注入代理变量
- `holo-cortex-zero-main/dockerfile`
  - 在前端构建阶段与 Python 构建阶段显式接收并导出代理环境
- `holo-cortex-zero-main/.env.example`
  - 补齐构建 / 运行统一代理示例

## 验证
- 锁文件包含 `dashscope`
- 容器内执行：
  - `import dashscope`
  - `from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer`
- 重建后主服务恢复 healthy

## 迁移审计
- Python 依赖来源：`pyproject.toml` + `uv.lock`
- 构建代理来源：根 `.env` 的 `HCZ_*_PROXY`
- 运行代理来源：`docker-compose.yml` 的容器环境
- 当前 `dockerfile` 已将主链基础镜像与 `uv` 搬运镜像固定到 digest
- 仍需外部环境保证的部分：Docker daemon 可访问这些已固定 digest 的远端镜像仓库
