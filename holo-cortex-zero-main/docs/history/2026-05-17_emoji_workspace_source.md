# Emoji Workspace Source Cleanup

## Background

The system emoji files were physically stored under:

```text
/path/to/runtime-data/system/emoji
```

The high-frequency operator path was:

```text
/path/to<CONTAINER_WORKSPACE_DIR>/emoji
```

Before this change, the operator path was only a symlink to the `srv` path. This made the source of truth ambiguous.

## Change

`/path/to<CONTAINER_WORKSPACE_DIR>/emoji` is now the real host directory for system emoji files.

The old `srv` emoji path was removed and must not be recreated as a source, fallback, or placeholder:

```text
/path/to/runtime-data/system/emoji
```

The main service runtime config now points directly at the workspace path:

```text
SYSTEM_EMOJI_HOST_DIR: <CONTAINER_WORKSPACE_DIR>/emoji
```

No bind mount is added under `<CONTAINER_DATA_DIR>/system/emoji`, because nesting a bind mount below `${HCZ_DATA_DIR}/system:<CONTAINER_DATA_DIR>/system` makes Docker recreate `/path/to/runtime-data/system/emoji` as an empty mount target on the host.

## Verification Targets

Expected state after recreating only `holo_cortex_zero`:

```text
/path/to<CONTAINER_WORKSPACE_DIR>/emoji                         exists, real directory, 98 files
/path/to/runtime-data/system/emoji absent
<CONTAINER_WORKSPACE_DIR>/emoji                               exists in container, 98 files
SYSTEM_EMOJI_HOST_DIR                          <CONTAINER_WORKSPACE_DIR>/emoji
```

Do not move emoji files back under `/path/to/runtime-data/system/emoji`.
