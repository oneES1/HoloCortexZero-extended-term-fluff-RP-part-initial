#!/bin/bash

# ============================================
# Language Selection / 语言选择
# ============================================

# Detect system language
detect_language() {
    case "${LANG:-}" in
        zh_CN*|zh_TW*|zh_HK*|zh_SG*)
            echo "zh"
            ;;
        *)
            echo "en"
            ;;
    esac
}

# Select language at startup
select_language() {
    echo "================================================"
    echo "Please select language / 请选择语言:"
    echo "  1) English"
    echo "  2) 简体中文"
    echo "================================================"
    read -r -p "Enter option (default: auto-detect) / 输入选项 (默认: 自动检测): " lang_choice
    echo ""
    
    case "$lang_choice" in
        1)
            LANG_SELECTED="en"
            ;;
        2)
            LANG_SELECTED="zh"
            ;;
        "")
            LANG_SELECTED=$(detect_language)
            ;;
        *)
            echo "Invalid option, using auto-detect / 无效选项，使用自动检测"
            LANG_SELECTED=$(detect_language)
            ;;
    esac
}

# Initialize language
select_language

# ============================================
# Text Translation Functions / 文本翻译函数
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
copy_local_file() {
    local source_path=$1
    local output_path=$2
    if [ ! -f "$source_path" ]; then
        echo "Error: local file not found / 本地文件不存在: $source_path" >&2
        return 1
    fi
    cp "$source_path" "$output_path"
}

ensure_hcz_data_dir() {
    local runtime_uid=${HCZ_RUNTIME_UID:-$(id -u)}
    local runtime_gid=${HCZ_RUNTIME_GID:-$(id -g)}

    if mkdir -p "$HCZ_DATA_DIR" 2>/dev/null; then
        chmod 2775 "$HCZ_DATA_DIR" 2>/dev/null || true
        return 0
    fi

    if command -v sudo >/dev/null 2>&1; then
        sudo mkdir -p "$HCZ_DATA_DIR" &&
            sudo chown "$runtime_uid:$runtime_gid" "$HCZ_DATA_DIR" &&
            sudo chmod 2775 "$HCZ_DATA_DIR"
        return $?
    fi

    return 1
}

seed_default_runtime_config() {
    local seed_config="${DEPLOY_ROOT}/holo-cortex-zero-main/default_configs/holo-cortex-zero.yaml"
    local target_dir="${HCZ_DATA_DIR}/configs"
    local target_config="${target_dir}/holo-cortex-zero.yaml"
    local runtime_uid=${HCZ_RUNTIME_UID:-$(id -u)}
    local runtime_gid=${HCZ_RUNTIME_GID:-$(id -g)}

    if [ ! -f "$seed_config" ]; then
        echo "Warn: default config seed missing, skipped / 默认配置种子不存在，跳过: $seed_config"
        return 0
    fi

    if [ -f "$target_config" ]; then
        echo "Runtime config already exists, skip seed / 运行配置已存在，跳过默认配置初始化: $target_config"
        return 0
    fi

    if ! mkdir -p "$target_dir" 2>/dev/null; then
        if command -v sudo >/dev/null 2>&1; then
            sudo mkdir -p "$target_dir" || return 1
            sudo chown "$runtime_uid:$runtime_gid" "$target_dir" 2>/dev/null || true
        else
            return 1
        fi
    fi

    if ! cp -n "$seed_config" "$target_config" 2>/dev/null; then
        if command -v sudo >/dev/null 2>&1; then
            sudo cp -n "$seed_config" "$target_config" || return 1
        else
            return 1
        fi
    fi
    chown "$runtime_uid:$runtime_gid" "$target_config" 2>/dev/null || sudo chown "$runtime_uid:$runtime_gid" "$target_config" 2>/dev/null || true
    chmod g+rw "$target_config" 2>/dev/null || true
    echo "Initialized default runtime config / 已初始化默认运行配置: $target_config"
}

seed_default_emoji_assets() {
    local seed_dir="${DEPLOY_ROOT}/holo-cortex-zero-main/default_workspace/emoji"
    local workspace_dir
    local emoji_dir
    local emoji_count
    local runtime_uid=${HCZ_RUNTIME_UID:-$(id -u)}
    local runtime_gid=${HCZ_RUNTIME_GID:-$(id -g)}

    if [ ! -d "$seed_dir" ]; then
        echo "Warn: default emoji seed dir missing, skipped / 默认 emoji 种子目录不存在，跳过: $seed_dir"
        return 0
    fi

    workspace_dir=$(grep -m1 '^HCZ_WORKSPACE_DIR=' .env | cut -d '=' -f2-)
    if [ -z "$workspace_dir" ]; then
        workspace_dir="./workspace"
    fi

    case "$workspace_dir" in
        /*) emoji_dir="${workspace_dir}/emoji" ;;
        *) emoji_dir="${DEPLOY_ROOT}/${workspace_dir}/emoji" ;;
    esac

    if ! mkdir -p "$emoji_dir" 2>/dev/null; then
        if command -v sudo >/dev/null 2>&1; then
            sudo mkdir -p "$emoji_dir" || return 1
            sudo chown "$runtime_uid:$runtime_gid" "$emoji_dir" 2>/dev/null || true
        else
            return 1
        fi
    fi

    emoji_count=$(find "$emoji_dir" -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ')
    if [ "$emoji_count" = "0" ]; then
        if ! cp -n "$seed_dir"/* "$emoji_dir"/ 2>/dev/null; then
            if command -v sudo >/dev/null 2>&1; then
                sudo cp -n "$seed_dir"/* "$emoji_dir"/ || return 1
            else
                return 1
            fi
        fi
        chown -R "$runtime_uid:$runtime_gid" "$emoji_dir" 2>/dev/null || sudo chown -R "$runtime_uid:$runtime_gid" "$emoji_dir" 2>/dev/null || true
        chmod g+rws "$emoji_dir" 2>/dev/null || true
        find "$emoji_dir" -type f -exec chmod g+rw {} + 2>/dev/null || true
        echo "Initialized default emoji assets / 已初始化默认 emoji 资源: $emoji_dir"
    else
        echo "Emoji dir already has ${emoji_count} file(s), skip seed / emoji 目录已有 ${emoji_count} 个文件，跳过默认资源初始化: $emoji_dir"
    fi
}

t() {
    local key="$1"
    case "$LANG_SELECTED" in
        zh)
            case "$key" in
                "unknown_option") echo "未知选项" ;;
                "download_failed_retry") echo "下载失败，尝试其他源..." ;;
                "select_docker_mirror") echo "请选择使用的 Docker 安装源：" ;;
                "docker_official") echo "Docker 官方" ;;
                "aliyun") echo "阿里" ;;
                "azure_china") echo "Azure 中国云" ;;
                "enter_option_default") echo "请输入选项数字 (默认为 1): " ;;
                "unknown_option_exit") echo "未知选项，退出..." ;;
                "warn_uninstall_docker") echo "Warn: 为避免冲突，Docker 官方安装脚本通常要求移除旧 Docker/容器运行时包。" ;;
                "confirm_uninstall_docker") echo "是否卸载 docker.io docker-doc docker-compose podman-docker containerd runc？" ;;
                "skipped_uninstall_docker") echo "已跳过卸载旧 Docker 包。若后续安装失败，请手动处理包冲突后重试。" ;;
                "confirm_official_script") echo "将从 https://get.docker.com 下载并执行 Docker 官方安装脚本，是否继续？" ;;
                "skipped_official_script") echo "已跳过 Docker 官方安装脚本。" ;;
                "try_get_docker_script") echo "尝试获取 Docker 安装脚本..." ;;
                "docker_script_downloaded") echo "Docker 安装脚本下载完成." ;;
                "docker_install_failed") echo "Docker 安装失败..." ;;
                "docker_script_download_failed") echo "Docker 安装脚本下载失败..." ;;
                "docker_script_download_retry") echo "Docker 安装脚本下载失败，正在重试" ;;
                "pkg_manager_not_apt") echo "包管理器非 apt，暂不支持..." ;;
                "confirm_fallback_install") echo "将执行 apt-get update 并安装 docker.io docker-compose，是否继续？" ;;
                "skipped_fallback_install") echo "已跳过 apt 备用安装。" ;;
                "updating_sources") echo "正在更新软件源..." ;;
                "error_update_sources") echo "Error: 更新软件源失败，请检查您的网络连接。" ;;
                "installing_docker") echo "正在安装 Docker..." ;;
                "error_docker_install") echo "Error: Docker 安装失败，请检查您的网络连接或软件源配置。" ;;
                "error_jq_not_installed") echo "Error: jq 未安装" ;;
                "error_daemon_json_invalid") echo "Error: /etc/docker/daemon.json 文件内容有误。" ;;
                "fix_or_delete_file") echo "请修复该文件或将其删除后重试。" ;;
                "error_jq_process_failed") echo "Error: jq 处理 JSON 失败。" ;;
                "error_write_daemon_json") echo "Error: 写入 /etc/docker/daemon.json 文件失败。" ;;
                "hcz_depends_docker") echo "HoloCortexZero 依赖于 Docker Compose，当前环境缺失" ;;
                "prefer_official_script") echo "优先使用 Docker 官方脚本进行安装" ;;
                "warn_manual_uninstall") echo "Warn: 您可能需要手动卸载已安装的 docker" ;;
                "confirm_assist_install") echo "是否让脚本辅助安装 Docker / Docker Compose？" ;;
                "cancelled") echo "已取消..." ;;
                "installing_via_official") echo "正在通过 Docker 官方安装脚本进行安装" ;;
                "trying_fallback") echo "正在尝试备用安装方式..." ;;
                "install_failed_exit") echo "安装失败，退出..." ;;
                "hcz_data_dir") echo "HCZ_DATA_DIR: " ;;
                "error_create_dir") echo "Error: 无法创建应用目录 $HCZ_DATA_DIR，请检查您的权限配置。" ;;
                "error_enter_dir") echo "Error: 无法进入应用目录 $HCZ_DATA_DIR。" ;;
                "env_not_found") echo "未找到.env文件，正在复制根目录 .env.share.example..." ;;
                "error_get_env_example") echo "Error: 无法获取根目录 .env.share.example 文件，请检查部署包完整性或手动创建 .env 文件。" ;;
                "error_copy_env") echo "Error: 无法将文件 .env.share.example 复制为 .env" ;;
                "error_hcz_port_not_set") echo "Error: HCZ_EXPOSE_PORT 未在 .env 文件中设置" ;;
                "confirm_env_config") echo "请检查并按需修改.env文件中的配置，未修改则按照默认配置安装，确认是否继续安装？[Y/n] " ;;
                "install_cancelled") echo "安装已取消..." ;;
                "confirm_daemon_mirrors") echo "是否修改 /etc/docker/daemon.json 添加 Docker 镜像源？这可能影响宿主所有 Docker 拉镜像行为。" ;;
                "confirm_install_jq") echo "jq 未安装，将执行 apt-get update 并安装 jq，是否继续？" ;;
                "skipped_install_jq") echo "已跳过安装 jq，无法自动修改 Docker 镜像源。" ;;
                "confirm_restart_docker") echo "已写入 Docker daemon 配置，是否现在重载 systemd 并重启 Docker？这会影响宿主正在运行的容器。" ;;
                "skipped_restart_docker") echo "已跳过重启 Docker。请在合适窗口手动执行 systemctl daemon-reload && systemctl restart docker。" ;;
                "error_add_failed") echo "Error: 添加失败" ;;
                "pulling_images") echo "拉取服务镜像..." ;;
                "error_pull_images") echo "Error: 无法拉取服务镜像，请检查您的网络连接。" ;;
                "using_instance_name") echo "使用实例名称: " ;;
                "starting_service") echo "启动主服务中..." ;;
                "error_start_service") echo "Error: 无法启动主服务，请检查 Docker Compose 配置。" ;;
                "error_env_not_exist") echo "Error: .env 文件不存在" ;;
                "need_allow_port") echo "HoloCortexZero 主服务需放行端口" ;;
                "configuring_firewall") echo "正在配置防火墙..." ;;
                "confirm_ufw") echo "是否通过 ufw 放行 ${HCZ_EXPOSE_PORT:-20261}/tcp？这会修改宿主防火墙规则。" ;;
                "skipped_ufw") echo "已跳过 ufw 防火墙配置。若服务访问受限，请手动放行 ${HCZ_EXPOSE_PORT:-20261}/tcp。" ;;
                "warn_firewall_failed") echo "Warning: 无法放行防火墙端口" ;;
                "warn_firewall_check") echo "，如服务访问受限，请检查防火墙设置。" ;;
                "deployment_complete") echo "=== 部署完成！===" ;;
                "view_logs") echo "你可以通过以下命令查看服务日志：" ;;
                "important_config") echo "=== 重要配置信息 ===" ;;
                "onebot_token") echo "OneBot 访问令牌: " ;;
                "admin_account") echo "管理员账号: " ;;
                "password_label") echo "密码: " ;;
                "service_access") echo "=== 服务访问信息 ===" ;;
                "hcz_port") echo "HoloCortexZero 主服务端口: " ;;
                "hcz_web_url") echo "HoloCortexZero Web 访问地址: " ;;
                "napcat_web_url") echo "NapCat WebUI 访问地址: " ;;
                "notes") echo "=== 注意事项 ===" ;;
                "note_1") echo "1. 如果您使用的是云服务器，请在云服务商控制台的安全组中放行以下端口：" ;;
                "note_hcz_port") echo "   - ${HCZ_EXPOSE_PORT:-20261}/tcp (HoloCortexZero 主服务)" ;;
                "note_2") echo "2. NapCat WebUI 默认通过 HCZ /napcat 内置反代访问，不需要单独开放 NapCat 端口" ;;
                "note_3") echo "3. 如果需要从外部访问，请将上述地址中的 127.0.0.1 替换为您的服务器公网IP" ;;
                "note_4") echo "4. 请使用 'sudo docker logs ${INSTANCE_NAME}hcz_napcat' 查看机器人 QQ 账号二维码进行登录" ;;
                "install_complete") echo "安装完成！祝您使用愉快！" ;;
                *) echo "$key" ;;
            esac
            ;;
        en)
            case "$key" in
                "unknown_option") echo "Unknown option" ;;
                "download_failed_retry") echo "Download failed, trying other sources..." ;;
                "select_docker_mirror") echo "Please select Docker installation source:" ;;
                "docker_official") echo "Docker Official" ;;
                "aliyun") echo "Aliyun" ;;
                "azure_china") echo "Azure China Cloud" ;;
                "enter_option_default") echo "Enter option number (default: 1): " ;;
                "unknown_option_exit") echo "Unknown option, exiting..." ;;
                "warn_uninstall_docker") echo "Warn: Docker's official installer usually requires removing old Docker/container runtime packages to avoid conflicts." ;;
                "confirm_uninstall_docker") echo "Remove docker.io docker-doc docker-compose podman-docker containerd runc?" ;;
                "skipped_uninstall_docker") echo "Skipped removing old Docker packages. If installation fails later, resolve package conflicts manually and retry." ;;
                "confirm_official_script") echo "Download and execute Docker official installer from https://get.docker.com?" ;;
                "skipped_official_script") echo "Skipped Docker official installer." ;;
                "try_get_docker_script") echo "Trying to get Docker installation script..." ;;
                "docker_script_downloaded") echo "Docker installation script downloaded." ;;
                "docker_install_failed") echo "Docker installation failed..." ;;
                "docker_script_download_failed") echo "Docker installation script download failed..." ;;
                "docker_script_download_retry") echo "Docker installation script download failed, retrying" ;;
                "pkg_manager_not_apt") echo "Package manager is not apt, not supported yet..." ;;
                "confirm_fallback_install") echo "Run apt-get update and install docker.io docker-compose?" ;;
                "skipped_fallback_install") echo "Skipped apt fallback installation." ;;
                "updating_sources") echo "Updating package sources..." ;;
                "error_update_sources") echo "Error: Failed to update package sources, please check your network connection." ;;
                "installing_docker") echo "Installing Docker..." ;;
                "error_docker_install") echo "Error: Docker installation failed, please check your network connection or package source configuration." ;;
                "error_jq_not_installed") echo "Error: jq is not installed" ;;
                "error_daemon_json_invalid") echo "Error: /etc/docker/daemon.json file content is invalid." ;;
                "fix_or_delete_file") echo "Please fix the file or delete it and try again." ;;
                "error_jq_process_failed") echo "Error: jq JSON processing failed." ;;
                "error_write_daemon_json") echo "Error: Failed to write /etc/docker/daemon.json file." ;;
                "hcz_depends_docker") echo "HoloCortexZero depends on Docker Compose, which is missing in the current environment" ;;
                "prefer_official_script") echo "Prefer to install using Docker official script" ;;
                "warn_manual_uninstall") echo "Warn: You may need to manually uninstall the installed docker" ;;
                "confirm_assist_install") echo "Let this script help install Docker / Docker Compose?" ;;
                "cancelled") echo "Cancelled..." ;;
                "installing_via_official") echo "Installing via Docker official script" ;;
                "trying_fallback") echo "Trying fallback installation method..." ;;
                "install_failed_exit") echo "Installation failed, exiting..." ;;
                "hcz_data_dir") echo "HCZ_DATA_DIR: " ;;
                "error_create_dir") echo "Error: Cannot create application directory $HCZ_DATA_DIR, please check your permissions." ;;
                "error_enter_dir") echo "Error: Cannot enter application directory $HCZ_DATA_DIR." ;;
                "env_not_found") echo ".env file not found, copying root .env.share.example..." ;;
                "error_get_env_example") echo "Error: Cannot find root .env.share.example, please check the deploy bundle or create .env manually." ;;
                "error_copy_env") echo "Error: Cannot copy file .env.share.example to .env" ;;
                "error_hcz_port_not_set") echo "Error: HCZ_EXPOSE_PORT is not set in .env file" ;;
                "confirm_env_config") echo "Please check and modify the configuration in .env file as needed. If not modified, install with default configuration. Continue installation? [Y/n] " ;;
                "install_cancelled") echo "Installation cancelled..." ;;
                "confirm_daemon_mirrors") echo "Modify /etc/docker/daemon.json to add Docker registry mirrors? This may affect all Docker pulls on the host." ;;
                "confirm_install_jq") echo "jq is missing. Run apt-get update and install jq?" ;;
                "skipped_install_jq") echo "Skipped installing jq; cannot automatically modify Docker registry mirrors." ;;
                "confirm_restart_docker") echo "Docker daemon config was written. Reload systemd and restart Docker now? This affects running host containers." ;;
                "skipped_restart_docker") echo "Skipped Docker restart. Run systemctl daemon-reload && systemctl restart docker manually in a maintenance window." ;;
                "error_add_failed") echo "Error: Add failed" ;;
                "pulling_images") echo "Pulling service images..." ;;
                "error_pull_images") echo "Error: Cannot pull service images, please check your network connection." ;;
                "using_instance_name") echo "Using instance name: " ;;
                "starting_service") echo "Starting main service..." ;;
                "error_start_service") echo "Error: Cannot start main service, please check Docker Compose configuration." ;;
                "error_env_not_exist") echo "Error: .env file does not exist" ;;
                "need_allow_port") echo "HoloCortexZero main service needs to allow port" ;;
                "configuring_firewall") echo "Configuring firewall..." ;;
                "confirm_ufw") echo "Allow ${HCZ_EXPOSE_PORT:-20261}/tcp through ufw? This changes host firewall rules." ;;
                "skipped_ufw") echo "Skipped ufw configuration. If service access is restricted, manually allow ${HCZ_EXPOSE_PORT:-20261}/tcp." ;;
                "warn_firewall_failed") echo "Warning: Cannot allow firewall port" ;;
                "warn_firewall_check") echo ", if service access is restricted, please check firewall settings." ;;
                "deployment_complete") echo "=== Deployment Complete! ===" ;;
                "view_logs") echo "You can view service logs with the following commands:" ;;
                "important_config") echo "=== Important Configuration Information ===" ;;
                "onebot_token") echo "OneBot Access Token: " ;;
                "admin_account") echo "Admin Account: " ;;
                "password_label") echo "Password: " ;;
                "service_access") echo "=== Service Access Information ===" ;;
                "hcz_port") echo "HoloCortexZero Main Service Port: " ;;
                "hcz_web_url") echo "HoloCortexZero Web Access URL: " ;;
                "napcat_web_url") echo "NapCat WebUI URL: " ;;
                "notes") echo "=== Notes ===" ;;
                "note_1") echo "1. If you are using a cloud server, please allow the following ports in the security group of your cloud provider's console:" ;;
                "note_hcz_port") echo "   - ${HCZ_EXPOSE_PORT:-20261}/tcp (HoloCortexZero Main Service)" ;;
                "note_2") echo "2. NapCat WebUI is served through the HCZ /napcat built-in proxy by default; no separate NapCat port is required." ;;
                "note_3") echo "3. If you need to access from outside, please replace 127.0.0.1 in the above addresses with your server's public IP" ;;
                "note_4") echo "4. Please use 'sudo docker logs ${INSTANCE_NAME}hcz_napcat' to view the QQ account QR code for bot login" ;;
                "install_complete") echo "Installation complete! Enjoy!" ;;
                *) echo "$key" ;;
            esac
            ;;
    esac
}

confirm_host_change() {
    local prompt=$1
    local default=${2:-n}
    local yn

    if [[ "$default" =~ ^[Yy]$ ]]; then
        read -r -p "$prompt [Y/n] " yn
        [ -z "$yn" ] && yn=y
    else
        read -r -p "$prompt [y/N] " yn
        [ -z "$yn" ] && yn=n
    fi
    echo ""
    [[ "$yn" =~ ^[Yy]$ ]]
}

# ============================================
# Original Script Logic / 原始脚本逻辑
# ============================================

# 解析命令行参数
if [[ "$#" -gt 0 ]]; then
    echo "$(t 'unknown_option'): $1"
    exit 1
fi

# Docker 镜像
DOCKER_IMAGE_MIRRORS=(
    "https://docker.m.daocloud.io"
    "https://docker.1ms.run"
    "https://ccr.ccs.tencentyun.com"
)

# 生成随机字符串的函数
generate_random_string() {
    local length=$1
    tr -dc 'a-zA-Z0-9' < /dev/urandom | fold -w "$length" | head -n 1
}

set_env_value() {
    local key=$1
    local value=$2
    if grep -q "^${key}=" .env; then
        sed -i "s|^${key}=.*|${key}=${value}|" .env
    else
        echo "${key}=${value}" >>.env
    fi
}

is_weak_postgres_password() {
    local value=${1:-}
    case "$value" in
        ""|change""_me_*|holo_cortex_zero)
            return 0
            ;;
    esac
    return 1
}

is_weak_admin_password() {
    local value=${1:-}
    case "$value" in
        ""|change""_me_*|123456)
            return 0
            ;;
    esac
    return 1
}

# 选择 Docker 安装镜像
select_docker_install_mirror() {
    echo "$(t 'select_docker_mirror')"
    echo "    1) $(t 'docker_official')"
    echo "    2) $(t 'aliyun')"
    echo "    3) $(t 'azure_china')"

    read -r -p "$(t 'enter_option_default')" num
    echo ""
    [ -z "$num" ] && num=1
    case "$num" in
        1)
            ;;
        2)
            DOCKER_PKG_MIRROR="Aliyun"
            ;;
        3)
            DOCKER_PKG_MIRROR="AzureChinaCloud"
            ;;
        *)
            >&2 echo "$(t 'unknown_option_exit')"
            exit 1
            ;;
    esac
}

# 通过脚本安装 docker
install_docker_via_official_script() {
    mirror="${1:-Aliyun}"
    max_retries=3
    attempt_num=0

    if command -v apt-get &>/dev/null; then
        echo "$(t 'warn_uninstall_docker')"
        if confirm_host_change "$(t 'confirm_uninstall_docker')" n; then
            for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do sudo apt-get remove "$pkg"; done
        else
            echo "$(t 'skipped_uninstall_docker')"
        fi
    fi
    if ! confirm_host_change "$(t 'confirm_official_script')" n; then
        echo "$(t 'skipped_official_script')"
        return 1
    fi
    echo "$(t 'try_get_docker_script')"
    while [ "$attempt_num" -le "$max_retries" ]; do
        if content=$(curl -fsSL -m 30 https://get.docker.com); then
            echo "$(t 'docker_script_downloaded')"
            # 使用 sed 命令修改 sleep 以取消等待
            if printf '%s\n' "$content" | sed 's#sleep#test#g' | sh -s -- --mirror "$mirror"; then
                DOCKER_COMPOSE_CMD="docker compose"
                return 0
            else
                echo "$(t 'docker_install_failed')" >&2
                return 1
            fi
        else
            if [ "$attempt_num" -eq "$max_retries" ]; then
                echo "$(t 'docker_script_download_failed')" >&2
                return 1
            fi
            echo "$(t 'docker_script_download_retry')($((attempt_num + 1))/$max_retries)"
            sleep 1
        fi
        attempt_num=$((attempt_num + 1))
    done
    return 1
}

# Docker 备用安装方式
install_docker_fallback() {
    if ! command -v apt-get &>/dev/null; then
        echo "$(t 'pkg_manager_not_apt')"
        return 1
    fi
    if ! confirm_host_change "$(t 'confirm_fallback_install')" n; then
        echo "$(t 'skipped_fallback_install')"
        return 1
    fi
    echo "$(t 'updating_sources')"
    if ! sudo apt-get update; then
        echo "$(t 'error_update_sources')"
        return 1
    fi
    echo "$(t 'installing_docker')"
    if ! sudo apt-get install -y docker.io docker-compose; then
        echo "$(t 'error_docker_install')" >&2
        return 1
    fi
    DOCKER_COMPOSE_CMD=docker-compose
}

# 添加 Docker 镜像源
add_docker_mirrors_prepend() {
    if [[ $# -eq 0 ]]; then
        return 1
    fi

    if ! command -v jq &> /dev/null; then
        echo "$(t 'error_jq_not_installed')" >&2
        return 1
    fi

    local daemon_file="/etc/docker/daemon.json"
    local current_json_input="{}"
    local mirrors_array_string="[]"
    if (($# > 0)); then
        mirrors_array_string=$(printf '%s\n' "$@" | jq -R . | jq -s .)
    fi

    if sudo test -f "$daemon_file" && sudo test -s "$daemon_file"; then
        if sudo jq -e 'type == "object"' "$daemon_file" >/dev/null 2>&1; then
            current_json_input=$(cat "$daemon_file")
        else
            echo "$(t 'error_daemon_json_invalid')" >&2
            echo "$(t 'fix_or_delete_file')" >&2
            return 1
        fi
        sudo cp "$daemon_file" "$daemon_file.bak"
    else
        sudo mkdir -p "/etc/docker/"
    fi

    local updated_json
    updated_json=$(echo "$current_json_input" | jq \
        --argjson new_mirrors_jq "$mirrors_array_string" \
        'if .["registry-mirrors"] != null and (.["registry-mirrors"] | type) != "array" then
                error("Error: daemon.json registry-mirrors exists but is not an array!")
        else
            .["registry-mirrors"] = ($new_mirrors_jq) + (.["registry-mirrors"] // [])
        end | .["registry-mirrors"] = ((.["registry-mirrors"] // []) | unique)'
    )

    # shellcheck disable=SC2181
    if [[ $? -ne 0 ]] || [[ -z "$updated_json" ]]; then
        echo "$(t 'error_jq_process_failed')" >&2
        return 1
    fi

    if echo "$updated_json" | sudo tee "$daemon_file" > /dev/null; then
        return 0
    fi
    echo "$(t 'error_write_daemon_json')" >&2
    return 1
}

DOCKER_COMPOSE_CMD=""
if command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE_CMD=docker-compose
elif docker compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
fi

# 安装 Docker
if ! command -v docker &>/dev/null && [[ -z $DOCKER_COMPOSE_CMD ]]; then
    echo "$(t 'hcz_depends_docker')"
    echo "$(t 'prefer_official_script')"
    if ! command -v apt-get &>/dev/null; then
        echo "$(t 'warn_manual_uninstall')"
    fi

    if ! confirm_host_change "$(t 'confirm_assist_install')" n; then
        echo "$(t 'cancelled')" >&2
        exit 1
    fi
    echo "$(t 'installing_via_official')"
    select_docker_install_mirror
    if ! install_docker_via_official_script "$DOCKER_PKG_MIRROR"; then
        echo "$(t 'docker_install_failed')" >&2
        echo "$(t 'trying_fallback')"
        if ! install_docker_fallback; then
            echo "$(t 'install_failed_exit')" >&2
            exit 1
        fi
    fi
fi

# 路径主干：
# - 部署根目录固定为脚本所在仓库的根目录
# - .env / docker-compose.yml 固定保留在部署根目录
# - HCZ_DATA_DIR 只承载运行数据，不再兼作部署根目录
#
# 设置应用目录 优先使用环境变量
if [ -z "$HCZ_DATA_DIR" ]; then
    HCZ_DATA_DIR="${DEPLOY_ROOT}/data"
fi

echo "HCZ_DEPLOY_ROOT: $DEPLOY_ROOT"
echo "$(t 'hcz_data_dir')$HCZ_DATA_DIR"

export HCZ_DATA_DIR=$HCZ_DATA_DIR

# 创建应用目录
ensure_hcz_data_dir || {
    echo "$(t 'error_create_dir')"
    exit 1
}


# 进入部署根目录
cd "$DEPLOY_ROOT" || {
    echo "Error: cannot enter deploy root / 无法进入部署根目录: $DEPLOY_ROOT"
    exit 1
}

# 如果当前目录没有 .env 文件，从部署根目录模板复制
if [ ! -f .env ]; then
    echo "Using root .env.share.example / 正在复制根目录 .env.share.example..."
    if ! copy_local_file "${DEPLOY_ROOT}/.env.share.example" .env.share.example; then
        echo "Error: root .env.share.example not found / 根目录 .env.share.example 不存在"
        exit 1
    fi
    if ! cp .env.share.example .env; then
        echo "$(t 'error_copy_env')"
        exit 1
    fi
fi

# 替换或添加 HCZ_DATA_DIR
if grep -q "^HCZ_DATA_DIR=" .env; then
    sed -i "s|^HCZ_DATA_DIR=.*|HCZ_DATA_DIR=${HCZ_DATA_DIR}|" .env
else
    echo "HCZ_DATA_DIR=${HCZ_DATA_DIR}" >>.env
fi

HCZ_RUNTIME_UID_VALUE=${HCZ_RUNTIME_UID:-$(id -u)}
HCZ_RUNTIME_GID_VALUE=${HCZ_RUNTIME_GID:-$(id -g)}
if grep -q "^HCZ_RUNTIME_UID=" .env; then
    sed -i "s|^HCZ_RUNTIME_UID=.*|HCZ_RUNTIME_UID=${HCZ_RUNTIME_UID_VALUE}|" .env
else
    echo "HCZ_RUNTIME_UID=${HCZ_RUNTIME_UID_VALUE}" >>.env
fi

if grep -q "^HCZ_RUNTIME_GID=" .env; then
    sed -i "s|^HCZ_RUNTIME_GID=.*|HCZ_RUNTIME_GID=${HCZ_RUNTIME_GID_VALUE}|" .env
else
    echo "HCZ_RUNTIME_GID=${HCZ_RUNTIME_GID_VALUE}" >>.env
fi


if grep -q "^HCZ_RUNTIME_UMASK=" .env; then
    sed -i "s|^HCZ_RUNTIME_UMASK=.*|HCZ_RUNTIME_UMASK=0002|" .env
else
    echo "HCZ_RUNTIME_UMASK=0002" >>.env
fi

seed_default_runtime_config || {
    echo "Error: failed to initialize default runtime config / 初始化默认运行配置失败"
    exit 1
}

seed_default_emoji_assets || {
    echo "Error: failed to initialize default emoji assets / 初始化默认 emoji 资源失败"
    exit 1
}

set -a
source ./.env
set +a
sudo -E bash "${SCRIPT_DIR}/init_runtime_permissions.sh"

# HCZ 一体化 NapCat 使用固定 OneBot token，避免新手配置 NapCat 与 NoneBot 两端密钥。
ONEBOT_ACCESS_TOKEN=$(grep -m1 '^ONEBOT_ACCESS_TOKEN=' .env | cut -d '=' -f2-)
if [ -z "$ONEBOT_ACCESS_TOKEN" ]; then
    set_env_value ONEBOT_ACCESS_TOKEN "?SA0WZ4HhGgnpT1("
fi

# 生成随机部署密码，覆盖空值、占位值和公开弱默认。
POSTGRES_PASSWORD=$(grep -m1 '^POSTGRES_PASSWORD=' .env | cut -d '=' -f2-)
if is_weak_postgres_password "$POSTGRES_PASSWORD"; then
    POSTGRES_PASSWORD=$(generate_random_string 32)
    set_env_value POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
fi

HCZ_ADMIN_PASSWORD=$(grep -m1 '^HCZ_ADMIN_PASSWORD=' .env | cut -d '=' -f2-)
if is_weak_admin_password "$HCZ_ADMIN_PASSWORD"; then
    HCZ_ADMIN_PASSWORD=$(generate_random_string 32)
    set_env_value HCZ_ADMIN_PASSWORD "$HCZ_ADMIN_PASSWORD"
fi

QDRANT_API_KEY=$(grep -m1 '^QDRANT_API_KEY=' .env | cut -d '=' -f2-)
if [ -z "$QDRANT_API_KEY" ]; then
    QDRANT_API_KEY=$(generate_random_string 32)
    set_env_value QDRANT_API_KEY "$QDRANT_API_KEY"
fi

# 从.env文件加载环境变量
# 设置 INSTANCE_NAME 默认值为空字符串
INSTANCE_NAME=$(grep -m1 '^INSTANCE_NAME=' .env | cut -d '=' -f2)
export INSTANCE_NAME=$INSTANCE_NAME

# 确保 HCZ_EXPOSE_PORT 有值
HCZ_EXPOSE_PORT=$(grep -m1 '^HCZ_EXPOSE_PORT=' .env | cut -d '=' -f2)
if [ -z "$HCZ_EXPOSE_PORT" ]; then
    echo "$(t 'error_hcz_port_not_set')"
    exit 1
fi
export HCZ_EXPOSE_PORT=$HCZ_EXPOSE_PORT

read -r -p "$(t 'confirm_env_config')" yn
echo ""
[ -z "$yn" ] && yn=y
if ! [[ "$yn" =~ ^[Yy]$ ]]; then
    echo -e "$(t 'install_cancelled')"
    exit 0
fi

# 添加 Docker 镜像到 daemon.json
if confirm_host_change "$(t 'confirm_daemon_mirrors')" n; then
    if ! command -v jq &>/dev/null; then
        if command -v apt-get &>/dev/null; then
            if confirm_host_change "$(t 'confirm_install_jq')" n; then
                sudo apt-get update && sudo apt-get install -y jq
            else
                echo "$(t 'skipped_install_jq')"
            fi
        else
            echo "$(t 'pkg_manager_not_apt')"
        fi
    fi
    if add_docker_mirrors_prepend "${DOCKER_IMAGE_MIRRORS[@]}"; then
        if confirm_host_change "$(t 'confirm_restart_docker')" n; then
            sudo systemctl daemon-reload
            sudo systemctl restart docker
        else
            echo "$(t 'skipped_restart_docker')"
        fi
    else
        echo "$(t 'error_add_failed')" >&2
    fi
fi

if [ ! -f docker-compose.yml ]; then
    echo "Error: canonical root docker-compose.yml missing / 缺少根目录 docker-compose.yml，请从部署包根目录运行安装脚本"
    exit 1
fi

# 本地构建主服务镜像
echo "Building local holo_cortex_zero image / 正在本地构建 holo_cortex_zero 镜像..."
if ! sudo bash -c "cd \"$DEPLOY_ROOT\" && $DOCKER_COMPOSE_CMD --env-file .env -f docker-compose.yml build holo_cortex_zero"; then
    echo "Error: failed to build local holo_cortex_zero image / 本地构建 holo_cortex_zero 镜像失败"
    exit 1
fi

# 从.env文件加载环境变量
if [ -f .env ]; then
    echo "$(t 'using_instance_name')${INSTANCE_NAME}"
    echo "$(t 'starting_service')"
    if ! sudo bash -c "cd \"$DEPLOY_ROOT\" && $DOCKER_COMPOSE_CMD --env-file .env -f docker-compose.yml up -d"; then
        echo "$(t 'error_start_service')"
        exit 1
    fi
else
    echo "$(t 'error_env_not_exist')"
    exit 1
fi

# 旧独立运行时已退役：这里不再拉取、不再构建相关镜像。
echo "Legacy detached runtime retired / 旧独立运行时已退役，跳过相关镜像处理。"

# 放行防火墙端口
echo "$(t 'need_allow_port') ${HCZ_EXPOSE_PORT:-20261}/tcp..."
if command -v ufw &>/dev/null; then
    if confirm_host_change "$(t 'confirm_ufw')" n; then
        echo -e "\n$(t 'configuring_firewall')"
        if ! sudo ufw allow "${HCZ_EXPOSE_PORT:-20261}/tcp"; then
            echo "$(t 'warn_firewall_failed') ${HCZ_EXPOSE_PORT:-20261}$(t 'warn_firewall_check')"
        fi
    else
        echo "$(t 'skipped_ufw')"
    fi
fi

echo -e "\n$(t 'deployment_complete')"
echo "$(t 'view_logs')"
echo "  HoloCortexZero: 'sudo docker logs -f ${INSTANCE_NAME}holo_cortex_zero'"
echo "  NapCat: 'sudo docker logs -f ${INSTANCE_NAME}hcz_napcat'"

# 显示重要的配置信息
echo -e "\n$(t 'important_config')"
ONEBOT_ACCESS_TOKEN=$(grep -m1 '^ONEBOT_ACCESS_TOKEN=' .env | cut -d '=' -f2-)
HCZ_ADMIN_PASSWORD=$(grep -m1 '^HCZ_ADMIN_PASSWORD=' .env | cut -d '=' -f2-)
HCZ_ADMIN_USERNAME=$(grep -m1 '^HCZ_ADMIN_USERNAME=' .env | cut -d '=' -f2-)
HCZ_ADMIN_USERNAME=${HCZ_ADMIN_USERNAME:-admin}
QDRANT_API_KEY=$(grep -m1 '^QDRANT_API_KEY=' .env | cut -d '=' -f2-)
echo "$(t 'onebot_token')${ONEBOT_ACCESS_TOKEN}"
echo "$(t 'admin_account')${HCZ_ADMIN_USERNAME} | $(t 'password_label')${HCZ_ADMIN_PASSWORD}"

echo -e "\n$(t 'service_access')"
echo "$(t 'hcz_port')${HCZ_EXPOSE_PORT:-20261}"
echo "$(t 'hcz_web_url')http://127.0.0.1:${HCZ_EXPOSE_PORT:-20261}"
echo "$(t 'napcat_web_url')http://127.0.0.1:${HCZ_EXPOSE_PORT:-20261}/napcat/webui/"

echo -e "\n$(t 'notes')"
echo "$(t 'note_1')"
echo "$(t 'note_hcz_port')"
echo "$(t 'note_2')"
echo "$(t 'note_3')"
echo "$(t 'note_4')"

echo -e "\n$(t 'install_complete')"
