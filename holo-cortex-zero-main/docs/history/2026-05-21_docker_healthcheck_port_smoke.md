# Docker Healthcheck Port Smoke Test

## Context

Open-source deploy bundle smoke testing used an isolated instance with `HCZ_EXPOSE_PORT=20271` to avoid colliding with the production service.

## Finding

The service started and `/api/health` returned 200 on port 20271, but Docker marked `smoke_holo_cortex_zero` as unhealthy because the image healthcheck still probed hard-coded port 20261.

## Change

Updated the Dockerfile healthcheck to probe `${PORT:-20261}`. Compose already sets `PORT=${HCZ_EXPOSE_PORT:-20261}`, so default deployments keep probing 20261, while changed-port deployments probe the configured runtime port.
