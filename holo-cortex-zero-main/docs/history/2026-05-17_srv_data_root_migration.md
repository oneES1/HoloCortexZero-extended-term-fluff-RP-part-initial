# Data Root Migration To /srv

## Background

The live HCZ data root used to be:

```text
/path/to/runtime-data
```

That path was a historical convenience default under the `ubuntu` home directory. It was not a separate mount and it made the service data root look like user workspace data.

## Change

The live data root is now:

```text
/path/to/runtime-data
```

The old data root must not be recreated:

```text
/path/to/runtime-data
```

High-frequency operator resources remain in the HCZ workspace:

```text
/path/to<CONTAINER_WORKSPACE_DIR>/logs
/path/to<CONTAINER_WORKSPACE_DIR>/emoji
```

Service state remains under `/path/to/runtime-data`, including configs, postgres, qdrant, napcat, system, uploads, tool state, backups, quarantine uploads, tmp, and container home.

## Permission Model

`hcz_permissions_init` remains as the startup safety net for HCZ-writable bind mounts. It does not manage `postgres_data` or `qdrant_data`.

Expected writable service directories are owned by the runtime UID/GID (`1000:1000`) with group-write/setgid permissions where applicable. Database-owned directories keep their service-specific ownership.

## Verification Targets

```text
/path/to/runtime-data                    exists
/path/to/runtime-data        absent
docker inspect mounts                    contain /path/to/runtime-data, not /path/to/runtime-data
holo_cortex_zero                         healthy
hcz_postgres, hcz_qdrant, hcz_napcat     running
```
