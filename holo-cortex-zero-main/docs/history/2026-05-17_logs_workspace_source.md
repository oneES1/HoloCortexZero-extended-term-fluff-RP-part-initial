# Logs Workspace Source Cleanup

## Background

HCZ runtime logs were stored under:

```text
/path/to/runtime-data/logs
```

That path made operator access inconsistent with other high-frequency workspace resources.

## Change

`/path/to<CONTAINER_WORKSPACE_DIR>/logs` is now the real host directory for runtime logs.

Both `hcz_permissions_init` and `holo_cortex_zero` mount it to the container runtime log path:

```yaml
./logs:<CONTAINER_DATA_DIR>/logs:rw
```

The old `srv` logs path was removed and must not be recreated as a source, fallback, or placeholder:

```text
/path/to/runtime-data/logs
```

## Verification Targets

Expected state after recreating only `holo_cortex_zero`:

```text
/path/to<CONTAINER_WORKSPACE_DIR>/logs                         exists, real directory
/path/to/runtime-data/logs        absent
<CONTAINER_DATA_DIR>/logs                                exists in container
```

Do not commit log files.
