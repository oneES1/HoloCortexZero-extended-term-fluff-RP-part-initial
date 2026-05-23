# 2026-05-21 Mac Desktop Native Audit

## Scope

This audit records Docker and public-server assumptions that affect a full native macOS desktop build. It is read-only analysis; no runtime code was changed in this step.

## Baseline

- Repository: `/home/ubuntu/hcz-deploy/holo-cortex-zero-main`
- Branch at audit time: `main`
- Previous planning commit: `3fbfe7c chore(docs): document mac desktop native plan`
- Commands used: `rg`, `sed`, `find`, `git`
- Exclusions: no full log reads, no Docker build, no service restart, no network download

## High-Impact Findings

| Area | File | Current fact | Desktop impact | Suggested treatment |
| --- | --- | --- | --- | --- |
| Python entry | `pyproject.toml:8`, `pyproject.toml:48` | Requires Python `>=3.11,<3.13`; script entry is `bot = "run_bot:main"`. | Desktop runtime should package CPython 3.11/3.12 and start the same entry. | Keep the entry common. Do not create a parallel backend launcher unless it only wraps env setup. |
| System packages | `dockerfile:73` | Docker image installs `libmagic-dev libolm-dev ffmpeg`. | macOS bundle must provide `libmagic.dylib`, `libolm.dylib`, `ffmpeg`, and `ffprobe`, or require them during early testing. | Verify with existing startup dependency check before app packaging. |
| Startup dependency check | `run_bot.py:61-90` | `check_required_system_dependencies()` runs during startup. | This is useful for desktop. It should fail early when native dylibs or media tools are missing. | Keep common. Improve hints later with macOS-specific install/bundle path text if needed. |
| Backend bind and port | `run_bot.py:117-144` | Host and port come from NoneBot config, defaulting to `0.0.0.0:20261`. | Desktop must bind loopback only. | Add run/auth mode guard before desktop release: desktop-local auth must reject non-loopback host. |
| Data and workspace | `holo_cortex_zero/core/os_env.py:9-18`, `holo_cortex_zero/core/os_env.py:24-32` | Workspace detection prefers `HCZ_WORKSPACE_ROOT`, then `/workspace`, then deployment ancestor. Data defaults to `./data`. | Desktop can already inject env, but `/workspace` fallback is Docker-shaped. | Desktop runtime must inject `HCZ_WORKSPACE_ROOT`/`WORKSPACE_ROOT` and `HCZ_DATA_DIR`/`DATA_DIR` explicitly. |
| Database env | `holo_cortex_zero/core/os_env.py:34-41`, `holo_cortex_zero/core/database.py:20-33` | Postgres is configurable by env/config; env defaults are localhost/5432 with weak password. | Desktop can target `127.0.0.1:55432`, but must generate strong local secrets. | No hard fork needed. Use desktop runtime env and local Postgres process. |
| Qdrant env | `holo_cortex_zero/core/os_env.py:43-46`, `holo_cortex_zero/core/vector_db.py:40-45` | Qdrant URL is configurable; env default is `http://localhost:6333`. | Desktop can target `127.0.0.1:56333`. | No hard fork needed. Use desktop runtime env and local Qdrant process. |
| Static assets | `holo_cortex_zero/core/os_env.py:65-66`, `dockerfile:37` | Static dir defaults to `./static`; Dockerfile copies built frontend dist into image static path. | Desktop must package `frontend/dist` and point `HCZ_STATIC_DIR`/`STATIC_DIR` at the app resource path. | Build frontend on Mac during first native verification, then package dist. |
| Server login | `holo_cortex_zero/routers/admin.py:30-61`, `holo_cortex_zero/services/platform_admin.py:35-48` | WebUI admin login checks `ADMIN_USERNAME` and `ADMIN_PASSWORD`, with rate limiting in the route. | Desktop should not show a login page, but deleting auth would expose local high-privilege APIs to other local processes. | Add common auth mode later: `password` for server, `desktop_local` for app-injected local session. |
| Protected APIs | `holo_cortex_zero/services/platform_admin.py:50-87` | Protected routes depend on bearer JWT in URL or Authorization header. | Desktop shell can inject a local token/session into WebView if the backend supports desktop-local auth. | Reuse JWT/session trunk, avoid a separate desktop-only permission system. |
| Weak secret rejection | `scripts/hcz_runtime_entrypoint.sh:23-29` | Docker entrypoint rejects empty/placeholder admin password and weak Postgres password. | This script is Docker-specific, but the policy is still valid for public server. Desktop should generate local secrets instead of asking the user to edit `.env`. | Keep Docker script unchanged. Add desktop runtime secret generation outside this script. |
| NapCat proxy default | `holo_cortex_zero/routers/napcat_proxy.py:12`, `holo_cortex_zero/adapters/onebot_v11/adapter.py:139-151` | Default backend-to-NapCat URL is `http://hcz_napcat:65535`; adapter config exposes `NAPCAT_PROXY_BASE_URL`. | Desktop target should be `http://127.0.0.1:56535`. | This is already configurable. Desktop settings should set it; later rename/doc env surface if needed. |
| NapCat container name | `holo_cortex_zero/adapters/onebot_v11/adapter.py:154-163` | Default container name is `hcz_napcat`. | Local-process NapCat has no container name. | Container status/log APIs need runtime-provider abstraction or desktop-mode graceful unavailability. |
| OneBot file path mapping | `holo_cortex_zero/adapters/onebot_v11/adapter.py:176-194` | Workspace paths are mapped to `/workspace`; NapCat QQ paths are mapped to `/app/.config/QQ`. | Native NapCat path rules may differ. | Must verify on Mac with real NapCat native runtime. Avoid rewriting until observed. |
| OneBot container APIs | `holo_cortex_zero/adapters/onebot_v11/routers.py:7-8`, `holo_cortex_zero/adapters/onebot_v11/routers.py:90-120`, `holo_cortex_zero/adapters/onebot_v11/routers.py:136-204` | Status/log/token routes use `aiodocker` and Docker containers. | These routes will fail in native desktop unless abstracted. | Add a runtime provider later: Docker provider for server, local-process provider for desktop. |
| Restart API | `holo_cortex_zero/routers/restart.py:11`, `holo_cortex_zero/routers/restart.py:24-32` | Restart calls Docker self-restart when `RUN_IN_DOCKER`; otherwise returns a manual restart error. | Desktop should delegate restart to the desktop runtime manager. | Add runtime provider or desktop supervisor hook later. |
| Docker utility | `holo_cortex_zero/tools/docker_util.py:4-88` | Container lookup/restart uses `aiodocker`. | Cannot be used as-is by native desktop. | Keep Docker utility, add a separate runtime interface above it rather than copying call sites. |
| Dev scripts | `scripts/dev_stack.sh:74-95`, `pyproject.toml:151-163` | Development dependency tasks assume Docker Compose. | Desktop repo should own native process orchestration. | Do not modify server dev flow during Linux preparation. |
| Proxy config | `holo_cortex_zero/core/config.py:2007-2021`, `holo_cortex_zero/core/proxy_utils.py` | `DEFAULT_PROXY` exists in common config. | Desktop can write config/env for proxies, but app-launched processes need explicit env injection. | First desktop release should support manual proxy settings and inject backend process env. |
| Media helpers | `holo_cortex_zero/services/llm/router.py:815-1050`, `holo_cortex_zero/services/llm/gemini.py:210-273`, `holo_cortex_zero/adapters/telegram/message_processor.py:539-577` | Runtime uses `ffmpeg`/`ffprobe` from `PATH`. | Desktop must put bundled media binaries on `PATH`. | Runtime manager should prepend app resource binary dir to `PATH`. |

## Suggested First Upstream Changes

These should be requested and implemented separately after the Mac native process chain starts producing real failures.

1. Add explicit `HCZ_RUN_MODE=server|desktop`.
2. Add explicit `HCZ_WEB_AUTH_MODE=password|desktop_local`.
3. Guard `desktop_local` auth so it only allows loopback binds.
4. Add runtime-provider abstraction for restart and NapCat status/log APIs.
5. Keep NapCat base URL fully configurable; do not special-case Docker or macOS in request logic.
6. Ensure desktop proxy configuration flows through the common proxy/config layer and child-process env injection.

## Must Be Verified On macOS

Linux cannot prove these items:

- `python-magic` loading `libmagic.dylib`.
- `matrix-nio[e2e]` loading `libolm.dylib`.
- `ffmpeg`/`ffprobe` discovery inside an app-launched process.
- Qdrant macOS binary health and storage path.
- PostgreSQL local data initialization and port conflict behavior.
- NapCat native runtime command, data paths, login flow, and WebUI port.
- Tauri/Electron WebView token/session injection behavior.
- Codesign/notarization effects on child process launch.

## Initial macOS Health Checks

```bash
curl -fsS http://127.0.0.1:20261/api/health
pg_isready -h 127.0.0.1 -p 55432
curl -fsS http://127.0.0.1:56333/healthz
curl -fsS http://127.0.0.1:56535/
```

The NapCat health URL is provisional and must be corrected after the real macOS native NapCat runtime is observed.

