# 2026-05-22 Release Bundle Refresh

## Context

The tracked Docker deployment archive was older than the current source tree.
The GitHub sharing repository needed a fresh release bundle matching the latest
README and source updates.

## Changes

- Generated `hcz-docker-deploy-20260522.tar.gz` from the current repository
  state.
- Removed the older tracked `hcz-docker-deploy-20260521.tar.gz` artifact so the
  repository exposes only one current deployment package.

## Verification

- `OUT_DIR=/home/ubuntu/hcz-deploy STAMP=20260522 ./make_docker_release_bundle.sh`
- New SHA256:
  `71de5024af530a3cb5654611eda1f463f8b93879abf26eeb521889df5bbe6cab`
- Archive entries: `492`
- Required release entries: `104`
- Excluded runtime and secret categories scan: `0` matches
