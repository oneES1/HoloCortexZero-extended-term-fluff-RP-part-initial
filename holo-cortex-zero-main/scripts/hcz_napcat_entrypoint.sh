#!/usr/bin/env bash
set -euo pipefail

runtime_uid="${HCZ_RUNTIME_UID:-1000}"
runtime_gid="${HCZ_RUNTIME_GID:-1000}"
umask_value="${HCZ_RUNTIME_UMASK:-0002}"
onebot_token="${ONEBOT_ACCESS_TOKEN:-?SA0WZ4HhGgnpT1(}"
onebot_url="${ONEBOT_WS_URL:-ws://holo_cortex_zero:20261/onebot/v11/ws}"
napcat_webui_port="${NAPCAT_WEBUI_PORT:-65535}"
napcat_webui_config="/app/napcat/config/webui.json"

if ! [[ "${napcat_webui_port}" =~ ^[0-9]+$ ]] || ((napcat_webui_port < 1 || napcat_webui_port > 65535)); then
  echo "[runtime:napcat] invalid NAPCAT_WEBUI_PORT=${napcat_webui_port}; expected 1-65535" >&2
  exit 1
fi

umask "${umask_value}"
echo "[runtime:napcat] uid=${runtime_uid} gid=${runtime_gid} umask=${umask_value}"

managed_dirs=(
  /app/data
  /workspace/shared
  /app/.config/QQ
  /app/napcat/config
)

for dir in "${managed_dirs[@]}"; do
  mkdir -p "${dir}"
  chown "${runtime_uid}:${runtime_gid}" "${dir}" 2>/dev/null || true
  chmod g+rws "${dir}" 2>/dev/null || true
done

write_onebot_config() {
  local target="$1"
  cat > "${target}" <<EOF
{
  "network": {
    "httpServers": [],
    "httpSseServers": [],
    "httpClients": [],
    "websocketServers": [],
    "websocketClients": [
      {
        "enable": true,
        "name": "HCZ",
        "url": "${onebot_url}",
        "reportSelfMessage": false,
        "messagePostFormat": "array",
        "token": "${onebot_token}",
        "debug": false,
        "heartInterval": 30000,
        "reconnectInterval": 10000
      }
    ],
    "plugins": []
  },
  "musicSignUrl": "",
  "enableLocalFile2Url": false,
  "parseMultMsg": false
}
EOF
  chown "${runtime_uid}:${runtime_gid}" "${target}" 2>/dev/null || true
  chmod g+rw "${target}" 2>/dev/null || true
}

write_webui_config() {
  local target="$1"
  local port="$2"
  local token
  mkdir -p "$(dirname "${target}")"
  # 主干：NapCat WebUI 只监听容器内网端口，由 HCZ /napcat 内置反代统一出入口。
  # 分支兼容：保留既有 webui.json 的 token/theme 等字段，仅收口 host/port 与基础开关。
  if [[ -f "${target}" ]]; then
    if grep -q '"host"' "${target}"; then
      sed -i -E 's/"host"[[:space:]]*:[[:space:]]*"[^"]*"/"host": "0.0.0.0"/' "${target}"
    else
      sed -i '1a\  "host": "0.0.0.0",' "${target}"
    fi

    if grep -q '"port"' "${target}"; then
      sed -i -E 's/"port"[[:space:]]*:[[:space:]]*[0-9]+/"port": '"${port}"'/' "${target}"
    else
      sed -i '1a\  "port": '"${port}"',' "${target}"
    fi
  else
    token="$(date +%s%N | sha256sum | cut -c1-12)"
    cat > "${target}" <<EOF
{
  "host": "0.0.0.0",
  "port": ${port},
  "token": "${token}",
  "loginRate": 10,
  "autoLoginAccount": "",
  "disableWebUI": false,
  "disableNonLANAccess": false
}
EOF
  fi
  chown "${runtime_uid}:${runtime_gid}" "${target}" 2>/dev/null || true
  chmod g+rw "${target}" 2>/dev/null || true
}

patch_napcat_login_guard() {
  local bundle="/app/napcat/napcat.mjs"
  local marker="HCZIsNapCatOnlineLogin"

  [[ -f "${bundle}" ]] || return 0
  if grep -q "${marker}" "${bundle}"; then
    return 0
  fi

  # 主干：禁止重复登录只代表仍有真实在线会话，不能把残留 QQLoginStatus 当作在线。
  # 分支兼容：保留 NapCat 原有二维码、密码、快捷登录流程，只收口登录守卫语义。
  perl -0pi -e '
    s/const QQCheckLoginStatusHandler = async \(_, res\) => \{/const HCZIsNapCatOnlineLogin = () => {\n  const oneBotContext = WebUiDataRuntime.getOneBotContext();\n  const selfInfo = oneBotContext?.core?.selfInfo;\n  return WebUiDataRuntime.getQQLoginStatus() && selfInfo?.online === true;\n};\nconst QQCheckLoginStatusHandler = async (_, res) => {/;
    s/if \(WebUiDataRuntime\.getQQLoginStatus\(\)\) \{\n    return sendError\(res, "QQ Is Logined"\);\n  \}/if (HCZIsNapCatOnlineLogin()) {\n    return sendError(res, "QQ Is Logined");\n  }/g;
    s/const isLogin = WebUiDataRuntime\.getQQLoginStatus\(\);\n  if \(isLogin\) \{\n    return sendError\(res, "QQ Is Logined"\);\n  \}/const isLogin = HCZIsNapCatOnlineLogin();\n  if (isLogin) {\n    return sendError(res, "QQ Is Logined");\n  }/g;
  ' "${bundle}"

  if ! grep -q "${marker}" "${bundle}"; then
    echo "[runtime:napcat] failed to patch NapCat login guard: marker not found" >&2
    exit 1
  fi
  if grep -n -B2 'QQ Is Logined' "${bundle}" | grep -q 'WebUiDataRuntime.getQQLoginStatus'; then
    echo "[runtime:napcat] failed to patch NapCat login guard: stale guard remains" >&2
    exit 1
  fi
  echo "[runtime:napcat] NapCat login guard patched"
}

# HCZ 一体化部署主干：NapCat 只反向连接本 compose 内的 OneBot v11 服务。
# 固定 token 同时由 HCZ/NoneBot 校验，避免安装脚本、WebUI、运行态 JSON 各持一份。
shopt -s nullglob
onebot_configs=(/app/napcat/config/onebot11_*.json)
if ((${#onebot_configs[@]} > 0)); then
  rm -f /app/napcat/config/onebot11.json
else
  onebot_configs=(/app/napcat/config/onebot11.json)
fi
for config_path in "${onebot_configs[@]}"; do
  write_onebot_config "${config_path}"
done
shopt -u nullglob
echo "[runtime:napcat] onebot_ws_url=${onebot_url} token_config_count=${#onebot_configs[@]}"
write_webui_config "${napcat_webui_config}" "${napcat_webui_port}"
patch_napcat_login_guard
echo "[runtime:napcat] webui_port=${napcat_webui_port} webui_config=${napcat_webui_config}"

exec bash entrypoint.sh
