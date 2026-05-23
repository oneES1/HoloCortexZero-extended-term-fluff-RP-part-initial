# Install Script Host Confirmations

## 背景

Docker 部署面向熟悉服务器环境的用户，宿主 Docker、Compose、包管理器、防火墙通常由部署者自行维护。

原安装脚本为了方便小白，会在部分路径中主动修改宿主环境，例如卸载旧 Docker 包、执行 `apt-get update`、安装 Docker / Compose、写入 `/path/to/docker-daemon-config.json`、重启 Docker、防火墙放行端口、OpenWrt 下载 Compose 或重启 firewall。

这些动作不是业务运行风险，但属于开源部署体验风险；第三方宿主上可能已有业务容器或自定义 Docker 配置。

## 变更

- `docker/install.sh` 新增 `confirm_host_change`。
- `docker/wrtinstall.sh` 新增 `confirm_host_change`。
- 默认需要显式确认的宿主修改动作：
  - 卸载 Docker / containerd / compose 相关包。
  - 下载并执行 `https://get.docker.com`。
  - 执行 `apt-get update` / `apt-get install` 安装 Docker、Compose 或 jq。
  - 修改 `/path/to/docker-daemon-config.json`。
  - `systemctl daemon-reload` 与 `systemctl restart docker`。
  - `ufw allow` 修改宿主防火墙。
  - OpenWrt `opkg update` / `opkg install docker-compose`。
  - OpenWrt 访问 GitHub release 下载 Compose 二进制。
  - OpenWrt `uci commit firewall` 与 firewall restart。
- `README_DEPLOY.md` 明确推荐手动 Docker Compose 部署，安装脚本是可选宿主初始化辅助。
- `.env.share.example` 补充构建镜像源变量。

## 验证

- `bash -n holo-cortex-zero-main/docker/install.sh`
- `busybox ash -n holo-cortex-zero-main/docker/wrtinstall.sh`
- `rg` 扫描宿主修改动作，确认高风险路径前存在确认提示。
