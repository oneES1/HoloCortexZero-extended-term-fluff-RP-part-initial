# Deploy Commands After Workspace Split

## Scope

After splitting runtime roles into separate roots, the active local commands were updated to avoid the old `/path/to<CONTAINER_WORKSPACE_DIR>` source/deploy path.

Current local roots:

- Deploy root: `/path/to/deploy-root`
- Source root: `/path/to/source-root`
- Human workspace: `/path/to<CONTAINER_WORKSPACE_DIR>`
- Runtime data: `/path/to/runtime-data`
- Compose env: `/path/to/deploy-root/.env`

## Command Policy

Local development now uses:

```bash
cd /path/to/source-root && uv run poe dev
```

Backend-only runtime refresh now uses:

```bash
cd /path/to/deploy-root && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

Dependency, Dockerfile, lockfile, and entrypoint changes use:

```bash
cd /path/to/deploy-root && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --build --force-recreate holo_cortex_zero
```

Frontend build still runs from the source root:

```bash
cd /path/to/source-root && pnpm --dir frontend build
```

Then refresh `holo_cortex_zero` with the backend-only runtime refresh command.

## Files Updated

- `/path/to/AGENTS.md`
- `docker-compose.yml`
- `holo-cortex-zero-main/docs/README_DEPLOY.md`
- `make_docker_release_bundle.sh`

## Verification

Static checks confirmed non-history operational docs no longer contain the old active commands:

- `/path/to<CONTAINER_WORKSPACE_DIR>/.env`
- `/path/to/source-root`
- `cd /path/to<CONTAINER_WORKSPACE_DIR>`
- `docker compose build holo_cortex_zero`
- `docker compose up -d --build --force-recreate holo_cortex_zero`
- `docker compose up -d --force-recreate holo_cortex_zero`

No containers were restarted for this documentation/script cleanup.
