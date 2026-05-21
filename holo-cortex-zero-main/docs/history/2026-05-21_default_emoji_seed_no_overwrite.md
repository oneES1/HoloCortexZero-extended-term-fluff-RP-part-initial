# 2026-05-21 default emoji seed without runtime overwrite

## Goal

Open-source Docker bundles should include default emoji assets, while rebuilds or restarts must not overwrite an existing runtime workspace.

## Changes

- Added default emoji seed assets under `default_workspace/emoji/`.
- Install scripts copy those seed assets into `${HCZ_WORKSPACE_DIR}/emoji` only when that directory has zero files.
- Docker images do not carry `/app/default_workspace`; container startup does not seed emoji.
- Existing runtime emoji files are never overwritten; non-empty `${HCZ_WORKSPACE_DIR}/emoji` is skipped.
- Release bundle validation requires 98 default seed emoji files under `HCZ/holo-cortex-zero-main/default_workspace/emoji/`.

## Runtime Safety

The production workspace `/home/ubuntu/HCZ/emoji` already contains 98 files. With this change, install scripts report a skip and leave those files untouched. Rebuilds and recreates do not touch emoji.
