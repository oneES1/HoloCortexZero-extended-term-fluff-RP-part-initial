# 2026-05-21 Release Bundle Refresh After WebP Fixes

## Context

After the GitHub release preparation, two LLM image payload fixes landed in the
source tree. The tracked Docker deployment tarball needed to be regenerated so
the published bundle matched the latest repository code.

## Changes

- Regenerated `/home/ubuntu/hcz-deploy/hcz-docker-deploy-20260521.tar.gz` from
  the current source tree.
- Kept the existing release bundle name so the GitHub repository points to a
  single current deployment artifact.

## Verification

- `OUT_DIR=/home/ubuntu/hcz-deploy STAMP=20260521 ./make_docker_release_bundle.sh`
- New SHA256:
  `12e8d20ea766fc27994dc0c20b67a19979a2dc774e9795f4f96ea313d22d9dfb`
- Archive entries: `492`
- Required release entries: `104`
- Excluded runtime and secret categories scan: `0` matches
