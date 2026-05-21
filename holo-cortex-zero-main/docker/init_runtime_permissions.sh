#!/usr/bin/env bash
set -euo pipefail

HCZ_DATA_DIR="${HCZ_DATA_DIR:-./data}"
HCZ_WORKSPACE_ROOT="${HCZ_WORKSPACE_ROOT:-/workspace}"
HCZ_RUNTIME_UID="${HCZ_RUNTIME_UID:-${SUDO_UID:-$(id -u)}}"
HCZ_RUNTIME_GID="${HCZ_RUNTIME_GID:-${SUDO_GID:-$(id -g)}}"
HCZ_SHARED_FILES_DIR="${HCZ_WORKSPACE_ROOT}/shared"
HCZ_DRAW_FILES_DIR="${HCZ_WORKSPACE_ROOT}/draw"

fix_tree() {
  local path="$1"
  mkdir -p "${path}"
  chown -R "${HCZ_RUNTIME_UID}:${HCZ_RUNTIME_GID}" "${path}"
  find "${path}" -type d -exec chmod 2775 {} +
  find "${path}" -type f -exec chmod g+rw {} +
}

app_owned_dirs=(
  "${HCZ_DATA_DIR}/configs"
  "${HCZ_DATA_DIR}/logs"
  "${HCZ_DATA_DIR}/uploads"
  "${HCZ_DATA_DIR}/tool_state"
  "${HCZ_DATA_DIR}/system"
  "${HCZ_DATA_DIR}/quarantine_uploads"
  "${HCZ_DATA_DIR}/tmp"
  "${HCZ_DATA_DIR}/backups"
  "${HCZ_DATA_DIR}/napcat_data"
  "${HCZ_SHARED_FILES_DIR}"
  "${HCZ_DRAW_FILES_DIR}"
)

for dir in "${app_owned_dirs[@]}"; do
  fix_tree "${dir}"
done
