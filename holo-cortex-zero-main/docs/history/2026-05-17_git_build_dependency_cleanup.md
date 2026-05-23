# Git and Build Dependency Cleanup

## 背景

系统依赖审查发现主服务没有 `GitPython` 调用，也没有 git 源依赖；Dockerfile 仍安装 `git`、`gcc`、`libpq-dev`。当前锁文件为主流 Linux/Python 目标提供 wheel，主服务数据库驱动使用 `asyncpg`，`psycopg2-binary` 仅用于 legacy 维护脚本。

## 变更

- 删除 Python 依赖 `gitpython`。
- 从锁文件移除 `gitpython`、`gitdb`、`smmap`。
- Dockerfile 删除系统包 `git`。
- Dockerfile 删除构建兜底包 `gcc`、`libpq-dev`。
- 保留 `gnupg`、`libmagic-dev`、`libolm-dev`、`ffmpeg`。

## 影响

- 减少运行镜像体积与无用依赖面。
- 不影响主服务运行时 Git 功能；主服务没有 GitPython 调用。
- 不影响主服务数据库连接；主服务使用 `asyncpg`。
- `psycopg2-binary` 暂保留，legacy 维护脚本仍可直接连接 Postgres。

## 验证

- `rg` 确认运行时代码无 `import git` / `from git` / `Repo(...)`。
- `uv sync --frozen --no-dev --dry-run`。
- `uv run python -m compileall holo_cortex_zero tool_runtime scripts run_bot.py`。
- Dockerfile 系统包删减需要后续镜像 build 验证。
