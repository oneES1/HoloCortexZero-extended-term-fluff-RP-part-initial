#!/usr/bin/env bash
set -euo pipefail

runtime_uid="${HCZ_RUNTIME_UID:-1000}"
runtime_gid="${HCZ_RUNTIME_GID:-1000}"
umask_value="${HCZ_RUNTIME_UMASK:-0002}"

reject_secret() {
  local name="$1"
  local value="$2"
  local weak_default="$3"

  case "${value}" in
    ""|change""_me_*)
      echo "[runtime:app] ERROR: ${name} is empty or still uses a placeholder value." >&2
      echo "[runtime:app] Set a strong value in .env or run the installer to generate one." >&2
      exit 1
      ;;
  esac

  if [ -n "${weak_default}" ] && [ "${value}" = "${weak_default}" ]; then
    echo "[runtime:app] ERROR: ${name} still uses public weak default '${weak_default}'." >&2
    echo "[runtime:app] Set a strong value in .env or run the installer to generate one." >&2
    exit 1
  fi
}

reject_secret "HCZ_ADMIN_PASSWORD" "${HCZ_ADMIN_PASSWORD:-}" "123456"
reject_secret "HCZ_POSTGRES_PASSWORD" "${HCZ_POSTGRES_PASSWORD:-}" "holo_cortex_zero"

export HOME=/app/data/home
umask "${umask_value}"
echo "[runtime:app] uid=${runtime_uid} gid=${runtime_gid} umask=${umask_value}"

managed_dirs=(
  /app/data/home
  /app/data/configs
  /app/data/logs
  /app/data/uploads
  /app/data/tool_state
  /app/data/system
  /app/data/quarantine_uploads
  /app/data/tmp
  /app/data/backups
  /workspace/shared
  /workspace/draw
)

for dir in "${managed_dirs[@]}"; do
  mkdir -p "${dir}"
  chown "${runtime_uid}:${runtime_gid}" "${dir}" 2>/dev/null || true
  chmod g+rws "${dir}" 2>/dev/null || true
done

exec /app/.venv/bin/bot --env=prod
