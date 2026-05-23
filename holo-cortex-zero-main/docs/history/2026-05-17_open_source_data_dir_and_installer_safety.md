# Open-source data dir defaults and installer host safety

## Context

Open-source review found two remaining deployment risks:

- Source and examples still defaulted HCZ data to an absolute Linux host path (`/path/to/runtime-data`).
- `docker/install_i18n.sh` still allowed host package removal, network installer execution, apt installs, Docker daemon changes, Docker restarts, and ufw changes without the same default-deny confirmations already added to `docker/install.sh`.

## Changes

- Source local default `HCZ_DATA_DIR` is now `./data`.
- Root `.env.example` and deploy `.env.share.example` now use `./data` as the example data directory.
- Install scripts now resolve an unset `HCZ_DATA_DIR` to `${PWD}/data` before writing `.env`, avoiding relative-path re-resolution after the script enters the data directory.
- Docker runtime behavior is unchanged when Compose injects `HCZ_DATA_DIR=<CONTAINER_DATA_DIR>` inside containers.
- Current production deployments can keep `/path/to/runtime-data` by setting `HCZ_DATA_DIR=/path/to/runtime-data` explicitly in ignored real `.env`.
- `docker/install_i18n.sh` now uses default-no host modification confirmations for:
  - removing old Docker/container runtime packages;
  - downloading and executing `https://get.docker.com`;
  - running `apt-get update` and installing Docker/Compose fallback packages;
  - installing `jq`;
  - writing Docker registry mirrors and restarting Docker;
  - adding ufw firewall rules.
- Deploy README now lists `install_i18n.sh` as an optional host-initialization helper too.
- Deploy README now documents the data-dir choice explicitly:
  - `./data` for local/open-source defaults;
  - explicit absolute paths such as `/path/to/runtime-data` for production servers.
- Deploy README now states installer host-modification prompts default to "no" and names ufw changes as a host-sensitive action.
- Deploy README was rewritten into a Chinese deployment tutorial with ordered steps for requirements, `.env` creation, data directories, build/start, NapCat, build mirrors/proxies, optional installer scripts, updates, backup, and troubleshooting.

## Verification

- Static shell parse:
  - `bash -n docker/install.sh`
  - `bash -n docker/install_i18n.sh`
  - `bash -n docker/wrtinstall.sh`
  - `bash -n docker/init_runtime_permissions.sh`
- Static grep confirms no active default assignment to `/path/to/runtime-data` remains in source/examples/install scripts except documentation that tells production users to opt in explicitly.
