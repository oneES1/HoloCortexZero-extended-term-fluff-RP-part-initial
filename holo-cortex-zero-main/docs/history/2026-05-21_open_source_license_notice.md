# 2026-05-21 Open Source License And Notice

## Context

Before the first GitHub sharing push, the repository needed a clear open source
license boundary and source attribution files. The release package script also
needed to follow the current root-level `README_DEPLOY.md` location.

## Changes

- Added root `LICENSE` using Apache License 2.0.
- Added root `NOTICE` to preserve HCZ initial source attribution.
- Added a minimal root `README.md` with deployment pointer and license summary.
- Allowed `README.md`, `LICENSE`, and `NOTICE` through the root `.gitignore`.
- Updated the Docker release bundle script to include governance files and read
  `README_DEPLOY.md` from the repository root.

## Verification

- `bash -n make_docker_release_bundle.sh`
- `OUT_DIR=/tmp/hcz_release_license_check STAMP=license-check ./make_docker_release_bundle.sh`
- Verified the generated archive contains `LICENSE`, `NOTICE`, `README.md`, and
  `README_DEPLOY.md`.
- Verified the generated archive still excludes `.env`, runtime data,
  database directories, caches, logs, `node_modules`, and `.venv`.
