# Deploy Doc First Run Paths

## Context

Open-source users need a clear first-run path that starts from the release tarball and explains which directories are source, runtime data, and workspace resources.

## Change

Expanded `README_DEPLOY.md` with tarball extraction steps, first-run directory layout, config/emoji seed copy behavior, model API key setup, and the fixed runtime path responsibilities.

## Notes

The documentation states that existing runtime config and emoji files are never overwritten, and that logs live under `${HCZ_DATA_DIR}/logs` instead of workspace.
