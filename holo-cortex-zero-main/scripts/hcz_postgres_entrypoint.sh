#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/lib/postgresql/14/bin:${PATH}"

case "${POSTGRES_PASSWORD:-}" in
  ""|change""_me_*|holo_cortex_zero)
    echo "[runtime:postgres] ERROR: POSTGRES_PASSWORD is empty, a placeholder, or the public weak default." >&2
    echo "[runtime:postgres] Set a strong value in .env or run the installer to generate one." >&2
    exit 1
    ;;
esac

mkdir -p /var/lib/postgresql/data
chown -R 999:999 /var/lib/postgresql/data
exec docker-entrypoint.sh postgres
