# Runtime Network Config Cleanup

## Goal

Business network configuration must have a single source of truth in HCZ runtime settings:

- Global outbound proxy: `DEFAULT_PROXY`
- Telegram proxy: `telegram/config.yaml` `PROXY_URL`
- LLM API endpoints: model-group `BASE_URL`
- Model proxy behavior: model-group `CHAT_PROXY` / `USE_GLOBAL_PROXY`

Docker Compose, `.env`, Docker bridge subnets, and image environment variables must not define business proxy or API endpoint behavior.

## Changes

- Removed `HCZ_HTTP_PROXY`, `HCZ_HTTPS_PROXY`, `HCZ_ALL_PROXY`, and `HCZ_NO_PROXY` from deployment examples and production `.env`.
- Removed Compose build/runtime injection of `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, and lowercase variants.
- Removed Dockerfile proxy ARG/ENV persistence so rebuilt runtime images do not carry proxy variables.
- Kept build-only apt/npm mirror arguments; these affect Docker image construction only and are not runtime business network settings.
- Added Matrix adapter `PROXY_URL`, default empty, so Matrix proxy behavior is adapter configuration instead of Docker environment fallback.
- Removed the runtime `preflight_socks.sh` entrypoint hop that inspected `HTTP_PROXY` / `ALL_PROXY`.
- Removed Telegram adapter fallback to process proxy environment variables; Telegram now uses only `PROXY_URL`.
- Removed startup normalization of process proxy environment variables from `core/os_env.py`.
- Set remaining direct `httpx.AsyncClient` call sites to `trust_env=False`, or routed them through the framework tool host HTTP bridge, so process environment proxies cannot silently affect business behavior.

## Boundary

Kept existing runtime settings under `/path/to/runtime-data/configs` because they are the intended production source of truth for current proxy and model API endpoints.

Kept build-only `HCZ_NPM_REGISTRY`, `HCZ_APT_DEBIAN_MIRROR`, `HCZ_APT_SECURITY_MIRROR`, and `HCZ_APT_NO_PROXY`; they are not business proxy/API settings and must not be injected into the runtime container environment.

## Verification

Required checks:

- `docker compose config` must not expand runtime `HTTP_PROXY` / `ALL_PROXY` values.
- Rebuilt image must not contain proxy ENV values.
- Running `holo_cortex_zero` container must not contain proxy ENV values.
- Tool HTTP must still use `DEFAULT_PROXY`.
- Telegram must report proxy source `config` when `PROXY_URL` is set.
- LLM local model calls must still use model-group `BASE_URL`.
- Container-to-container communication must still use service names, independent from Docker subnet selection.
