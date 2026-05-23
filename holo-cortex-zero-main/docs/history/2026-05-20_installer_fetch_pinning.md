# 2026-05-20 安装器远端拉取收口

## 问题

开源前审查时，安装链仍有三处不够稳的动态来源：

- `docker/install.ps1` 会从 GitHub raw 拉取 `docker/wslinstall.ps1`
- `docker/wslinstall.ps1` 会在 WSL 内再从 GitHub raw 拉取 `docker/install.sh`
- `docker/wrtinstall.sh` 会查询 GitHub `docker/compose` 的 `releases/latest` 再下载 Compose 二进制

## 调整

- `docker/install.ps1` 改为只调用同目录的 `wslinstall.ps1`
- `docker/wslinstall.ps1` 改为把同目录 `install.sh` 的 Windows 路径转换成 WSL 路径，再直接执行本地脚本
- `docker/wrtinstall.sh` 固定 Docker Compose 版本到 `v2.27.1`，不再查询 `latest`
- `docs/README_DEPLOY.md` 补了一句，说明 Windows / WSL 辅助入口现在也是仓库本地脚本链，不再远端拉中转脚本

## 验证

- `bash -n holo-cortex-zero-main/docker/wrtinstall.sh`
- `git diff --check`
- `rg -n "raw.githubusercontent.com|api.github.com/repos/docker/compose/releases/latest|/home/hcz/install.sh|latest" holo-cortex-zero-main/docker/install.ps1 holo-cortex-zero-main/docker/wslinstall.ps1 holo-cortex-zero-main/docker/wrtinstall.sh`
  - 仅剩 `latest` 一处出现在注释里，没有再出现远端下载 URL 或 GitHub latest API 调用

## 备注

- 这轮没有改 `install.sh` / `install_i18n.sh` 里的 `get.docker.com`，那部分仍然是人工确认后才会执行的 Docker 安装流程
- 当前环境没有 `pwsh`，因此本轮没有做 PowerShell 解析检查
