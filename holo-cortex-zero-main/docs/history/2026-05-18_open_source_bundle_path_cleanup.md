# 2026-05-18 open-source bundle path cleanup

## Scope

- Focus only on open-source facing path hygiene.
- No runtime service restart.
- No live config rewrite under `/path/to/runtime-data`.

## Problems addressed

1. `make_docker_release_bundle.sh` used a host-specific default output path under a concrete home directory.
2. Release bundle export still relied on negative filtering without explicitly excluding local runtime `configs/`.
3. Deploy README described the deploy root correctly, but `docker/install.sh`, `docker/install_i18n.sh`, and `docker/wrtinstall.sh` still treated `HCZ_DATA_DIR` as both data root and deploy root.

## Changes

- `make_docker_release_bundle.sh`
  - Default output root changed to `${TMPDIR:-/tmp}/hcz_release`.
  - Explicitly excludes `holo-cortex-zero-main/configs`.
  - Validation now rejects bundles that still contain `configs/`.
- `docker/install.sh`
  - Canonical deploy root is now the repo/bundle root (`SCRIPT_DIR/../..`).
  - `.env` is created from root `.env.share.example`.
  - `docker-compose.yml` is expected in the deploy root instead of being copied into `HCZ_DATA_DIR`.
  - `HCZ_DATA_DIR` remains data-only.
- `docker/install_i18n.sh`
  - Same canonical deploy-root behavior as `install.sh`.
- `docker/wrtinstall.sh`
  - Same canonical deploy-root behavior as `install.sh`.
- `docs/README_DEPLOY.md`
  - Clarifies that `.env` lives beside `docker-compose.yml`.
  - Clarifies that `HCZ_DATA_DIR` is not the deploy root.
  - Adds an explicit warning not to stage live config backups into the source tree or deploy root.

## Verification

- `bash -n docker/install.sh`
- `bash -n docker/install_i18n.sh`
- `busybox ash -n docker/wrtinstall.sh`
- `bash -n /path/to/deploy-root/make_docker_release_bundle.sh`

## Risk

- Users who previously relied on the installer writing `.env` into `HCZ_DATA_DIR` must now run the installer from the deploy root as documented.
- This is intentional: it removes the deploy-root/data-root ambiguity instead of preserving two parallel meanings.

## Rollback

- Revert this commit to restore the old installer behavior and old release-bundle default output path.
