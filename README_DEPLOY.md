# HCZ Docker 部署教程

这份文档用于从 HCZ Docker 发布包完成部署。发布包不包含运行数据、密钥、日志、上传文件、PostgreSQL 数据、Qdrant 数据、NapCat / QQ 登录态、自设图私有素材；这些内容会在部署机器上生成。

## 1. 最短流程

宿主机先安装：

- Docker Engine
- Docker Compose Plugin，确认 `docker compose version` 可用

把发布包放到一个独立目录并解压。假设发布包文件名是 `hcz-docker-deploy-YYYYMMDD.tar.gz`：

```bash
mkdir -p ~/hcz
cd ~/hcz
tar -xzf /path/to/hcz-docker-deploy-YYYYMMDD.tar.gz
cd HCZ
```

进入 `HCZ/` 后，这个目录下应至少有：

```text
docker-compose.yml
.env.share.example
README_DEPLOY.md
holo-cortex-zero-main/
```

创建运行环境文件：

```bash
cp .env.share.example .env
```

编辑 `.env`，至少把这两个密码改成自己的强密码：

```env
POSTGRES_PASSWORD=change_me_postgres_password
HCZ_ADMIN_PASSWORD=change_me_admin_password
```

首次启动前不要保留 `change_me_*` 占位值。容器启动脚本会拒绝空值、`change_me_*` 占位值和公开弱默认。

然后执行首次部署：

```bash
bash holo-cortex-zero-main/docker/install.sh
```

国内服务器可以使用国内构建源开关：

```bash
bash holo-cortex-zero-main/docker/install.sh cn
```

`cn` 会把 npm、uv、apt 的构建期镜像源写入 `.env`，只影响 Docker 构建下载依赖，不进入运行态业务配置。

查看状态：

```bash
docker compose ps
docker logs --tail 200 holo_cortex_zero
```

访问 Web UI：

```text
http://127.0.0.1:20261
```

远程服务器把 `127.0.0.1` 换成服务器地址，并确认防火墙或云安全组放行 `.env` 里的 `HCZ_EXPOSE_PORT`，默认是 `20261/tcp`。

## 2. 目录规则

`HCZ/` 是部署包根目录。`.env` 必须和 `docker-compose.yml` 放在同一级，不要放到 `data/` 或其他运行目录里。

`.env.share.example` 中的默认路径是：

```env
HCZ_DATA_DIR=./data
HCZ_WORKSPACE_DIR=./workspace
HCZ_SOURCE_DIR=./holo-cortex-zero-main
```

安装脚本会把 `HCZ_DATA_DIR` 写成部署目录下 `data` 的绝对路径；`HCZ_WORKSPACE_DIR` 和 `HCZ_SOURCE_DIR` 可以继续保留相对路径。首次部署后目录大致如下：

```text
HCZ/
├── .env
├── .env.share.example
├── README_DEPLOY.md
├── docker-compose.yml
├── holo-cortex-zero-main/
│   ├── default_configs/
│   │   └── holo-cortex-zero.yaml
│   ├── default_workspace/
│   │   └── emoji/*.png
│   └── ...
├── data/
│   ├── configs/
│   │   └── holo-cortex-zero.yaml
│   ├── logs/
│   ├── uploads/
│   ├── postgres_data/
│   ├── qdrant_data/
│   └── napcat_data/
└── workspace/
    ├── emoji/*.png
    ├── draw/
    └── shared/
```

路径职责固定为：

```text
源码: holo-cortex-zero-main/
运行配置: ${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml
运行日志: ${HCZ_DATA_DIR}/logs
工作区资源: ${HCZ_WORKSPACE_DIR}
默认表情运行态: ${HCZ_WORKSPACE_DIR}/emoji
```

`HCZ_DATA_DIR` 会保存数据库、向量库、上传文件、运行配置、备份、工具状态、NapCat 登录态等运行数据。`HCZ_WORKSPACE_DIR` 用于 `emoji/`、`draw/`、`shared/` 等资源目录；不要在 `workspace/` 中放置 `logs/`。

服务器长期运行时，也可以在首次启动前手动指定数据目录和工作区目录：

```env
HCZ_DATA_DIR=/path/to/runtime-data
HCZ_WORKSPACE_DIR=/srv/hcz_workspace
```

安装脚本首次部署时会做两项初始化：

- 如果 `${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml` 不存在，复制 `holo-cortex-zero-main/default_configs/holo-cortex-zero.yaml`
- 如果 `${HCZ_WORKSPACE_DIR}/emoji` 为空，复制 `holo-cortex-zero-main/default_workspace/emoji/`

已有运行配置或已有表情文件时都会跳过。容器重建、重启和日常更新不会重新播种，也不会覆盖已有配置或已有表情。

## 3. 配置模型

发布包里的默认配置会带模型组结构，例如：

```text
doubao
deepseek-v4-flash
deepseek-v4-pro
embedding-v4
gemini
```

为了避免泄露密钥，发布包里的默认配置已经清空所有 API key。首次部署后，请在 Web UI 或运行态配置文件中填入自己的模型密钥：

```text
${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml
```

保留默认相对路径时就是：

```text
HCZ/data/configs/holo-cortex-zero.yaml
```

至少需要补齐当前使用的聊天模型组和向量模型组，例如：

```yaml
MODEL_GROUPS:
  deepseek-v4-flash:
    API_KEY: "your_deepseek_key"
  embedding-v4:
    API_KEY: "your_embedding_key"
```

没有填 API key 时，服务仍可启动，Web UI 和基础管理功能可访问；需要 LLM 或记忆向量能力的功能会提示配置不完整或调用失败。

## 4. QQ / NapCat

`docker-compose.yml` 默认包含 NapCat 服务。NapCat Web UI 默认不开放宿主端口，由 HCZ 后端内置反代统一入口：

```text
http://127.0.0.1:20261/napcat/webui/
```

远程部署时仍只需要放行 HCZ 主服务端口，默认是 `20261/tcp`。NapCat 容器内监听端口默认是 `65535`，只在 Docker 网络内被 HCZ 访问。

查看 NapCat 登录二维码相关日志：

```bash
docker logs --tail 200 hcz_napcat
```

如果不使用 QQ / NapCat，可以只启动核心服务：

```bash
docker compose up -d hcz_postgres hcz_qdrant holo_cortex_zero
```

## 5. 国内构建源与代理

默认构建使用官方源，不固定国内镜像，也不要求代理。

国内服务器可以直接使用国内构建源开关：

```bash
bash holo-cortex-zero-main/docker/install.sh cn
```

`cn` 会写入以下构建期镜像源：

```env
HCZ_NPM_REGISTRY=https://registry.npmmirror.com
HCZ_UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple
HCZ_APT_DEBIAN_MIRROR=http://mirrors.cloud.tencent.com/debian
HCZ_APT_SECURITY_MIRROR=http://mirrors.cloud.tencent.com/debian-security
HCZ_APT_NO_PROXY=true
```

如果不使用安装脚本，也可以手动把这些项写进 `.env`。

如果 Docker build 容器需要访问宿主机代理，可以设置：

```env
HCZ_BUILD_NETWORK=host
HCZ_BUILD_HTTP_PROXY=http://<LOCAL_HTTP_PROXY>
HCZ_BUILD_HTTPS_PROXY=http://<LOCAL_HTTP_PROXY>
```

这些变量只用于 `docker build`。不要把 LLM API、Telegram 代理、Tavily、Matrix 等业务运行配置写到这些 build-only 变量里。业务运行配置应放在 `HCZ_DATA_DIR` 下生成的运行配置文件中。

## 6. 安装脚本与手动 Compose

推荐首次部署使用安装脚本：

```bash
bash holo-cortex-zero-main/docker/install.sh
```

也可以按语言或软路由环境选择：

```bash
bash holo-cortex-zero-main/docker/install_i18n.sh
bash holo-cortex-zero-main/docker/wrtinstall.sh
```

国内服务器使用辅助脚本时可以执行：

```bash
bash holo-cortex-zero-main/docker/install.sh cn
```

这些脚本固定以部署包根目录为主干：

- 读取根目录 `docker-compose.yml`
- 读取根目录 `.env.share.example`
- 生成或使用根目录 `.env`
- 仅把 `${HCZ_DATA_DIR}` 当作运行数据目录
- 首次部署时把源码默认配置复制到 `${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml`，已存在则跳过
- 首次部署时把源码默认表情复制到 `${HCZ_WORKSPACE_DIR}/emoji`，非空则跳过

请从部署包根目录运行脚本，不要在 `${HCZ_DATA_DIR}` 里运行，也不要把现网 `configs/`、`holo-cortex-zero.yaml.bak*`、`crypto_store/` 之类运行配置备份复制进源码树或部署包根目录。

辅助脚本可能会询问是否修改宿主环境，默认回答都是“否”。敏感动作包括：

- 安装或卸载 Docker 相关包
- 执行 `apt-get update`、`apt-get install`、`opkg update`、`opkg install`
- 下载 Docker 安装脚本或 Docker Compose 二进制文件
- 写入 `/etc/docker/daemon.json`
- 重启 Docker
- 修改 `ufw` 规则
- 提交并重启 OpenWrt firewall

如果宿主机已经运行重要容器，不要在业务时间让脚本重启 Docker。

如果明确不用安装脚本，也可以手动执行：

```bash
cp .env.share.example .env
docker compose up -d --build
```

手动 Compose 不会初始化默认运行配置和默认 emoji。需要默认配置和默认表情时，请先自行把 `holo-cortex-zero-main/default_configs/holo-cortex-zero.yaml` 复制到 `${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml`，把 `holo-cortex-zero-main/default_workspace/emoji/` 复制到 `${HCZ_WORKSPACE_DIR}/emoji`，且不要覆盖已有文件。

Windows/WSL 辅助入口 `holo-cortex-zero-main/docker/install.ps1` 只会调用同目录的 `wslinstall.ps1`，而 `wslinstall.ps1` 再调用同目录的 `install.sh`；它们不会从 GitHub 远端拉中转脚本。

## 7. 日常更新

普通源码更新后：

```bash
docker compose up -d --no-deps --force-recreate holo_cortex_zero
```

依赖、Dockerfile、锁文件、入口脚本变化后：

```bash
docker compose up -d --no-deps --build --force-recreate holo_cortex_zero
```

查看日志：

```bash
docker logs --tail 200 holo_cortex_zero
```

停止服务：

```bash
docker compose down
```

不要删除 `${HCZ_DATA_DIR}`，除非明确要清空运行数据。

## 8. 备份

建议定期备份：

```text
${HCZ_DATA_DIR}/configs
${HCZ_DATA_DIR}/postgres_data
${HCZ_DATA_DIR}/qdrant_data
${HCZ_DATA_DIR}/napcat_data
${HCZ_DATA_DIR}/uploads
${HCZ_DATA_DIR}/system
${HCZ_WORKSPACE_DIR}
```

最重要的是运行配置、数据库、向量库、上传文件和登录态。

## 9. 常见排查

容器没启动：

```bash
docker compose ps
docker logs --tail 200 holo_cortex_zero
docker logs --tail 200 hcz_postgres
docker logs --tail 200 hcz_qdrant
```

如果日志提示 `change_me`、`public weak default` 或密码占位值，请先修改 `.env` 里的 `POSTGRES_PASSWORD` 和 `HCZ_ADMIN_PASSWORD`，再重新执行：

```bash
docker compose up -d --build
```

Web UI 打不开：

- 检查 `.env` 里的 `HCZ_EXPOSE_PORT`
- 检查 `docker compose ps` 里 `holo_cortex_zero` 是否运行
- 检查防火墙或云安全组是否放行端口

构建下载依赖失败：

- 在 `.env` 中设置构建期镜像源
- 网络需要代理时设置构建期代理
- 重新执行 `docker compose up -d --build`

Linux 权限异常：

- 把 `.env` 中 `HCZ_RUNTIME_UID` 和 `HCZ_RUNTIME_GID` 改成应拥有运行文件的宿主用户/用户组
- 重新执行 `docker compose up -d --build`

`docker-compose.yml` 中的 PostgreSQL、Qdrant、NapCat 第三方镜像使用 digest 固定到已验证版本。以后如果手动升级这些 digest，必须重新验证 `docker compose ps`、健康检查和 NapCat WebUI 入口。
