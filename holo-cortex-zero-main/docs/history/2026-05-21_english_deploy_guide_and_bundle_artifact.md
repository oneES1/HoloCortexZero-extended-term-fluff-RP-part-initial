# 2026-05-21 English Deploy Guide And Bundle Artifact

## Context

The GitHub repository needed a tracked release bundle artifact and an English
deployment guide before wider project sharing.

## Changes

- Added root `README_DEPLOY_EN.md` as the English Docker deployment guide.
- Linked the English guide from root `README.md` and the Chinese deployment
  guide.
- Allowed `README_DEPLOY_EN.md` and `hcz-docker-deploy-*.tar.gz` through the
  root `.gitignore`.
- Updated `make_docker_release_bundle.sh` to copy and validate the English
  deployment guide inside the generated release bundle.
- Regenerated `/home/ubuntu/hcz-deploy/hcz-docker-deploy-20260521.tar.gz` so
  the tracked bundle contains the current license, notice, README, and
  bilingual deployment guides.

## Verification

- `bash -n make_docker_release_bundle.sh`
- `OUT_DIR=/home/ubuntu/hcz-deploy STAMP=20260521 ./make_docker_release_bundle.sh`
- Verified the generated archive contains `LICENSE`, `NOTICE`, `README.md`,
  `README_DEPLOY.md`, `README_DEPLOY_EN.md`, the default config seed, and 98
  default emoji assets.
- Verified the generated archive still excludes `.env`, runtime data,
  database directories, caches, logs, `node_modules`, and `.venv`.
