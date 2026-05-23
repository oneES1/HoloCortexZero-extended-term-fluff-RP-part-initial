# HCZ Docker Deployment Guide

This guide explains how to deploy HCZ from the Docker release bundle. The
release bundle does not include runtime data, secrets, logs, uploads,
PostgreSQL data, Qdrant data, NapCat / QQ login state, private self-image
assets, or personal runtime files. Those files are generated on the deployment
machine.

## 1. Quick Start

Install these prerequisites on the host machine:

- Docker Engine
- Docker Compose Plugin, with `docker compose version` available

Place the release bundle in an independent directory and extract it. Assuming
the bundle is named `hcz-docker-deploy-YYYYMMDD.tar.gz`:

```bash
mkdir -p ~/hcz
cd ~/hcz
tar -xzf /path/to/hcz-docker-deploy-YYYYMMDD.tar.gz
cd HCZ
```

After entering `HCZ/`, the directory should contain at least:

```text
docker-compose.yml
.env.share.example
README_DEPLOY.md
README_DEPLOY_EN.md
holo-cortex-zero-main/
```

Create the runtime environment file:

```bash
cp .env.share.example .env
```

Edit `.env` and replace at least these two passwords with strong private
values:

```env
POSTGRES_PASSWORD=change_me_postgres_password
HCZ_ADMIN_PASSWORD=change_me_admin_password
```

Do not keep any `change_me_*` placeholder values before the first startup. The
container startup script rejects empty values, `change_me_*` placeholders, and
public weak defaults.

Then run the first deployment:

```bash
bash holo-cortex-zero-main/docker/install.sh
```

For servers in mainland China, you can use the China build-source switch:

```bash
bash holo-cortex-zero-main/docker/install.sh cn
```

The `cn` switch writes npm, uv, and apt build-time mirrors into `.env`. These
settings only affect dependency downloads during Docker build and are not used
as runtime business configuration.

Check service status:

```bash
docker compose ps
docker logs --tail 200 holo_cortex_zero
```

Open the Web UI:

```text
http://127.0.0.1:20261
```

For remote servers, replace `127.0.0.1` with the server address and make sure
the firewall or cloud security group allows the port configured by
`HCZ_EXPOSE_PORT` in `.env`. The default is `20261/tcp`.

## 2. Directory Rules

`HCZ/` is the deployment bundle root. `.env` must stay beside
`docker-compose.yml`; do not place it under `data/` or another runtime
directory.

The default paths in `.env.share.example` are:

```env
HCZ_DATA_DIR=./data
HCZ_WORKSPACE_DIR=./workspace
HCZ_SOURCE_DIR=./holo-cortex-zero-main
```

The install script rewrites `HCZ_DATA_DIR` to an absolute `data` path under the
deployment directory. `HCZ_WORKSPACE_DIR` and `HCZ_SOURCE_DIR` may remain
relative paths. After first deployment, the directory layout is roughly:

```text
HCZ/
├── .env
├── .env.share.example
├── README_DEPLOY.md
├── README_DEPLOY_EN.md
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

Path responsibilities are fixed:

```text
Source code: holo-cortex-zero-main/
Runtime config: ${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml
Runtime logs: ${HCZ_DATA_DIR}/logs
Workspace assets: ${HCZ_WORKSPACE_DIR}
Runtime default emoji: ${HCZ_WORKSPACE_DIR}/emoji
```

`HCZ_DATA_DIR` stores databases, vector data, uploads, runtime configuration,
backups, tool state, NapCat login state, and other runtime data.
`HCZ_WORKSPACE_DIR` is used for `emoji/`, `draw/`, `shared/`, and related
workspace assets. Do not put `logs/` under `workspace/`.

For long-running servers, you may set explicit runtime and workspace paths
before first startup:

```env
HCZ_DATA_DIR=/path/to/runtime-data
HCZ_WORKSPACE_DIR=/srv/hcz_workspace
```

During first deployment, the install script performs two initialization steps:

- If `${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml` does not exist, it copies
  `holo-cortex-zero-main/default_configs/holo-cortex-zero.yaml`.
- If `${HCZ_WORKSPACE_DIR}/emoji` is empty, it copies
  `holo-cortex-zero-main/default_workspace/emoji/`.

If runtime configuration or emoji files already exist, the script skips them.
Container rebuilds, restarts, and daily updates do not reseed or overwrite
existing runtime configuration or existing emoji files.

## 3. Model Configuration

The default configuration in the release bundle includes model groups such as:

```text
doubao
deepseek-v4-flash
deepseek-v4-pro
embedding-v4
gemini
```

To avoid leaking secrets, all API keys in the release default configuration are
blank. After first deployment, fill in your own model keys through the Web UI
or the runtime configuration file:

```text
${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml
```

With the default relative path, this is:

```text
HCZ/data/configs/holo-cortex-zero.yaml
```

At minimum, configure the chat model group and embedding model group you plan
to use. Example:

```yaml
MODEL_GROUPS:
  deepseek-v4-flash:
    API_KEY: "your_deepseek_key"
  embedding-v4:
    API_KEY: "your_embedding_key"
```

The service can still start without API keys, and the Web UI plus basic admin
features remain available. Features that require LLM calls or vector memory
will report incomplete configuration or call failures until keys are provided.

## 4. QQ / NapCat

`docker-compose.yml` includes the NapCat service by default. The NapCat Web UI
does not expose a host port by default. HCZ provides an internal reverse proxy
entry:

```text
http://127.0.0.1:20261/napcat/webui/
```

For remote deployment, you still only need to expose the main HCZ service port,
which defaults to `20261/tcp`. NapCat listens on port `65535` inside the Docker
network and is accessed by HCZ there.

View NapCat QR-code/login related logs:

```bash
docker logs --tail 200 hcz_napcat
```

If you do not use QQ / NapCat, you can start only the core services:

```bash
docker compose up -d hcz_postgres hcz_qdrant holo_cortex_zero
```

## 5. Build Mirrors And Proxies

The default build uses official sources. It does not require China mirrors or a
proxy.

For servers in mainland China, use:

```bash
bash holo-cortex-zero-main/docker/install.sh cn
```

The `cn` switch writes these build-time mirror settings:

```env
HCZ_NPM_REGISTRY=https://registry.npmmirror.com
HCZ_UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple
HCZ_APT_DEBIAN_MIRROR=http://mirrors.cloud.tencent.com/debian
HCZ_APT_SECURITY_MIRROR=http://mirrors.cloud.tencent.com/debian-security
HCZ_APT_NO_PROXY=true
```

If you do not use the install script, you can write these values into `.env`
manually.

If the Docker build container needs access to a host proxy, set:

```env
HCZ_BUILD_NETWORK=host
HCZ_BUILD_HTTP_PROXY=http://<LOCAL_HTTP_PROXY>
HCZ_BUILD_HTTPS_PROXY=http://<LOCAL_HTTP_PROXY>
```

These variables are only used by `docker build`. Do not put LLM API proxies,
Telegram proxies, Tavily settings, Matrix settings, or other runtime business
configuration into these build-only variables. Runtime business configuration
belongs in the generated runtime configuration file under `HCZ_DATA_DIR`.

## 6. Install Scripts And Manual Compose

The recommended first deployment path is:

```bash
bash holo-cortex-zero-main/docker/install.sh
```

Alternative helper scripts are available for i18n or soft-router environments:

```bash
bash holo-cortex-zero-main/docker/install_i18n.sh
bash holo-cortex-zero-main/docker/wrtinstall.sh
```

For servers in mainland China, use the helper switch:

```bash
bash holo-cortex-zero-main/docker/install.sh cn
```

These scripts use the deployment bundle root as the single main path:

- Read root `docker-compose.yml`
- Read root `.env.share.example`
- Generate or use root `.env`
- Treat only `${HCZ_DATA_DIR}` as the runtime data directory
- On first deployment, copy the source default config to
  `${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml` if it does not already exist
- On first deployment, copy the source default emoji to
  `${HCZ_WORKSPACE_DIR}/emoji` if it is empty

Run the scripts from the deployment bundle root. Do not run them inside
`${HCZ_DATA_DIR}`. Do not copy production `configs/`,
`holo-cortex-zero.yaml.bak*`, `crypto_store/`, or other runtime backup files
into the source tree or deployment bundle root.

Helper scripts may ask whether they should modify the host environment. The
default answer is "no". Sensitive actions include:

- Installing or uninstalling Docker-related packages
- Running `apt-get update`, `apt-get install`, `opkg update`, or `opkg install`
- Downloading Docker install scripts or Docker Compose binaries
- Writing `/etc/docker/daemon.json`
- Restarting Docker
- Modifying `ufw` rules
- Committing and restarting the OpenWrt firewall

If the host already runs important containers, do not let the script restart
Docker during business hours.

If you explicitly choose not to use the install script, you can run Compose
manually:

```bash
cp .env.share.example .env
docker compose up -d --build
```

Manual Compose does not initialize the default runtime configuration or default
emoji. If you need the defaults, copy
`holo-cortex-zero-main/default_configs/holo-cortex-zero.yaml` to
`${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml`, and copy
`holo-cortex-zero-main/default_workspace/emoji/` to
`${HCZ_WORKSPACE_DIR}/emoji` yourself. Do not overwrite existing files.

The Windows/WSL helper entry `holo-cortex-zero-main/docker/install.ps1` only
calls `wslinstall.ps1` from the same directory, and `wslinstall.ps1` calls
`install.sh` from the same directory. They do not download an intermediate
script from GitHub.

## 7. Daily Updates

After ordinary source updates:

```bash
docker compose up -d --no-deps --force-recreate holo_cortex_zero
```

After dependency, Dockerfile, lockfile, or entrypoint-script changes:

```bash
docker compose up -d --no-deps --build --force-recreate holo_cortex_zero
```

View logs:

```bash
docker logs --tail 200 holo_cortex_zero
```

Stop services:

```bash
docker compose down
```

Do not delete `${HCZ_DATA_DIR}` unless you intentionally want to wipe runtime
data.

## 8. Backups

Back up these paths regularly:

```text
${HCZ_DATA_DIR}/configs
${HCZ_DATA_DIR}/postgres_data
${HCZ_DATA_DIR}/qdrant_data
${HCZ_DATA_DIR}/napcat_data
${HCZ_DATA_DIR}/uploads
${HCZ_DATA_DIR}/system
${HCZ_WORKSPACE_DIR}
```

The most important assets are runtime configuration, databases, vector data,
uploads, and login state.

## 9. Troubleshooting

Container does not start:

```bash
docker compose ps
docker logs --tail 200 holo_cortex_zero
docker logs --tail 200 hcz_postgres
docker logs --tail 200 hcz_qdrant
```

If logs mention `change_me`, `public weak default`, or password placeholders,
edit `POSTGRES_PASSWORD` and `HCZ_ADMIN_PASSWORD` in `.env`, then run:

```bash
docker compose up -d --build
```

Web UI cannot be opened:

- Check `HCZ_EXPOSE_PORT` in `.env`
- Check whether `holo_cortex_zero` is running in `docker compose ps`
- Check whether the firewall or cloud security group allows the port

Dependency downloads fail during build:

- Set build-time mirrors in `.env`
- Set build-time proxy variables if the network requires a proxy
- Run `docker compose up -d --build` again

Linux permission errors:

- Set `HCZ_RUNTIME_UID` and `HCZ_RUNTIME_GID` in `.env` to the host user/group
  that should own runtime files
- Run `docker compose up -d --build` again

The PostgreSQL, Qdrant, and NapCat third-party images in `docker-compose.yml`
are pinned to verified versions by digest. If you manually upgrade these
digests later, re-verify `docker compose ps`, health checks, and the NapCat
WebUI entry.
