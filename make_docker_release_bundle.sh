#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
STAMP=${STAMP:-$(date +%Y%m%d)}
BUNDLE_NAME=${BUNDLE_NAME:-hcz-docker-deploy-${STAMP}}
OUT_DIR=${OUT_DIR:-${TMPDIR:-/tmp}/hcz_release}
WORK_DIR="${OUT_DIR}/${BUNDLE_NAME}"
ARCHIVE_PATH="${OUT_DIR}/${BUNDLE_NAME}.tar.gz"

log() {
  printf '[release-bundle] %s\n' "$*"
}

require_path() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    log "缺少必需路径: $path"
    exit 1
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log "缺少命令: $cmd"
    exit 1
  fi
}

require_cmd rsync
require_cmd tar
require_cmd find
require_cmd python3

require_path "${ROOT_DIR}/docker-compose.yml"
require_path "${ROOT_DIR}/.env.share.example"
require_path "${ROOT_DIR}/holo-cortex-zero-main/docs/README_DEPLOY.md"
require_path "${ROOT_DIR}/holo-cortex-zero-main"
require_path "${ROOT_DIR}/holo-cortex-zero-main/default_workspace/emoji"
require_path "${ROOT_DIR}/holo-cortex-zero-main/data/configs/holo-cortex-zero.yaml"

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}/HCZ"

log '复制部署必需内容'
rsync -a "${ROOT_DIR}/docker-compose.yml" "${WORK_DIR}/HCZ/"
rsync -a "${ROOT_DIR}/.env.share.example" "${WORK_DIR}/HCZ/"
rsync -a "${ROOT_DIR}/holo-cortex-zero-main/docs/README_DEPLOY.md" "${WORK_DIR}/HCZ/README_DEPLOY.md"
rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.ruff_cache' \
  --exclude '.mypy_cache' \
  --exclude '.env' \
  --exclude '.env.dev' \
  --exclude 'configs' \
  --exclude 'data' \
  --exclude 'docs' \
  --exclude 'frontend/dist' \
  --exclude 'frontend/node_modules' \
  --exclude 'docker/docker-compose.dev.yml' \
  --exclude 'stage1_smoke' \
  --exclude 'scripts/__pycache__' \
  --exclude 'scripts/hcz_qwen35' \
  --exclude 'scripts/dev_stack.sh' \
  --exclude 'scripts/drop_legacy_preset_schema.py' \
  --exclude 'scripts/fix_i18n*.py' \
  --exclude 'scripts/smoke_*.py' \
  --exclude 'scripts/validate_*.py' \
  --exclude 'scripts/validation' \
  --exclude 'scripts/trigger_onebot_group_message.py' \
  --exclude 'scripts/utils.py' \
  --exclude '*.log' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  "${ROOT_DIR}/holo-cortex-zero-main" "${WORK_DIR}/HCZ/"

log '清理不应分享的内容'
find "${WORK_DIR}/HCZ" -type d \( \
  -name .git -o \
  -name .venv -o \
  -name node_modules -o \
  -name __pycache__ -o \
  -name .pytest_cache -o \
  -name .ruff_cache -o \
  -name .mypy_cache \
\) -prune -exec rm -rf {} +

find "${WORK_DIR}/HCZ" -type f \( \
  -name '.env' -o \
  -name '.env.dev' -o \
  -name '*.log' -o \
  -name '*.pyc' -o \
  -name '*.pyo' \
\) -delete

rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/data"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/configs"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/docs"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/frontend/dist"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/frontend/node_modules"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/docker/docker-compose.dev.yml"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/scripts/__pycache__"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/scripts/hcz_qwen35"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/scripts/validation"
rm -rf "${WORK_DIR}/HCZ/holo-cortex-zero-main/stage1_smoke"

find "${WORK_DIR}/HCZ/holo-cortex-zero-main/scripts" -maxdepth 1 -type f \( \
  -name 'dev_stack.sh' -o \
  -name 'drop_legacy_preset_schema.py' -o \
  -name 'fix_i18n*.py' -o \
  -name 'smoke_*.py' -o \
  -name 'validate_*.py' -o \
  -name 'trigger_onebot_group_message.py' -o \
  -name 'utils.py' \
\) -delete

log '生成开源默认配置种子'
mkdir -p "${WORK_DIR}/HCZ/holo-cortex-zero-main/default_configs"
python3 - "${ROOT_DIR}/holo-cortex-zero-main/data/configs/holo-cortex-zero.yaml" \
  "${WORK_DIR}/HCZ/holo-cortex-zero-main/default_configs/holo-cortex-zero.yaml" <<'PY'
from pathlib import Path
import sys
import yaml

source = Path(sys.argv[1])
target = Path(sys.argv[2])
data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}

secret_exact = (
    "API_KEY",
    "ACCESS_TOKEN",
    "ONEBOT_ACCESS_TOKEN",
    "ONEBOT_V11_ACCESS_TOKEN",
    "PASSWORD",
    "SECRET",
    "COOKIE",
    "PRIVATE_KEY",
    "ACCESS_KEY",
)
secret_suffixes = (
    "_API_KEY",
    "_ACCESS_TOKEN",
    "_PASSWORD",
    "_SECRET",
    "_COOKIE",
    "_PRIVATE_KEY",
    "_ACCESS_KEY",
)
string_blank_if_null = (
    "ADVANCED_USER_DISPLAY_NAME",
    "DEFAULT_PROXY",
    "GROUP_NAME",
    "CHAT_MODEL",
    "CHAT_PROXY",
    "BASE_URL",
    "API_KEY",
    "MODEL_TYPE",
    "REASONING_MODE",
    "TEXT_VERBOSITY",
    "WIRE_API",
    "CACHE_TRANSPORT_PROFILE",
    "REASONING_EFFORT",
)


def scrub(value, key_name=""):
    if isinstance(value, dict):
        cleaned = {}
        for key, child in value.items():
            key_text = str(key).upper()
            if key_text in secret_exact or any(key_text.endswith(suffix) for suffix in secret_suffixes):
                cleaned[key] = ""
            else:
                cleaned[key] = scrub(child, key_text)
        return cleaned
    if isinstance(value, list):
        return [scrub(item, key_name) for item in value]
    if value is None and key_name in string_blank_if_null:
        return ""
    return value


cleaned = scrub(data)
target.write_text(
    yaml.safe_dump(cleaned, allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)
PY

mkdir -p "${OUT_DIR}"
rm -f "${ARCHIVE_PATH}"

log '生成压缩包'
tar -C "${WORK_DIR}" -czf "${ARCHIVE_PATH}" HCZ

log '做最小校验'
if tar -tzf "${ARCHIVE_PATH}" | rg -q '(^|/)\.env$|(^|/)\.env\.dev$|(^|/)(configs/|srv/|postgres_data/|qdrant_data/|napcat_data/|node_modules/|\.venv/|docs/|self_image/|frontend/dist/|docker/docker-compose\.dev\.yml|scripts/hcz_qwen35/|scripts/validation/|scripts/dev_stack\.sh|scripts/drop_legacy_preset_schema\.py|scripts/fix_i18n[^/]*\.py|scripts/smoke_[^/]+\.py|scripts/validate_[^/]+\.py|scripts/trigger_onebot_group_message\.py|scripts/utils\.py)' ; then
  log '压缩包中仍包含不应分享的内容'
  exit 1
fi

if [[ "$(tar -tzf "${ARCHIVE_PATH}" | rg -c '^HCZ/holo-cortex-zero-main/default_configs/holo-cortex-zero\.yaml$')" != "1" ]]; then
  log '压缩包缺少开源默认配置种子'
  exit 1
fi

if [[ "$(tar -tzf "${ARCHIVE_PATH}" | rg -c '^HCZ/holo-cortex-zero-main/default_workspace/emoji/[^/]+$')" != "98" ]]; then
  log '压缩包中的默认 emoji 种子资源数量不是 98'
  exit 1
fi

rm -rf "${WORK_DIR}"

log "完成: ${ARCHIVE_PATH}"
log '预览:'
tar -tzf "${ARCHIVE_PATH}" | sed -n '1,80p'
