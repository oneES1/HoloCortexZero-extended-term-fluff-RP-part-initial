# Workspace Source Deploy Split

## Target

`/path/to<CONTAINER_WORKSPACE_DIR>` is reserved for the human workspace and the container `<CONTAINER_WORKSPACE_DIR>` mount source:

```text
/path/to<CONTAINER_WORKSPACE_DIR>/logs
/path/to<CONTAINER_WORKSPACE_DIR>/emoji
/path/to<CONTAINER_WORKSPACE_DIR>/self_image
/path/to<CONTAINER_WORKSPACE_DIR>/draw
/path/to<CONTAINER_WORKSPACE_DIR>/hpc_shared
```

Source and deployment files are no longer rooted inside `/path/to<CONTAINER_WORKSPACE_DIR>`.

## Runtime Variables

The compose deployment now separates these roots:

```text
COMPOSE_PROJECT_NAME=hcz
HCZ_WORKSPACE_DIR=/path/to<CONTAINER_WORKSPACE_DIR>
HCZ_SOURCE_DIR=/path/to/source-root
HCZ_DATA_DIR=/path/to/runtime-data
```

Open-source examples default to:

```text
COMPOSE_PROJECT_NAME=hcz
HCZ_WORKSPACE_DIR=.<CONTAINER_WORKSPACE_DIR>
HCZ_SOURCE_DIR=./holo-cortex-zero-main
HCZ_DATA_DIR=/path/to/runtime-data
```

## Notes

`HCZ_STATIC_DIR` now points to `/app/frontend/dist`, backed by an explicit read-only bind mount from `${HCZ_SOURCE_DIR}/frontend/dist`. This avoids depending on `<CONTAINER_WORKSPACE_DIR>/holo-cortex-zero-main`.

Runtime logs are mounted from `${HCZ_WORKSPACE_DIR}/logs`, not from the deploy directory.

`self_image` is also a workspace resource and must live under `${HCZ_WORKSPACE_DIR}/self_image`, not under the deploy root.

The context window workspace anchors no longer include `holo-cortex-zero-main`.
