#!/bin/bash

# 现行主干固定使用根目录 docker-compose.yml，其中已包含 napcat 服务
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_REGION=${HCZ_BUILD_REGION:-}
copy_local_file() {
    local source_path=$1
    local output_path=$2
    if [ ! -f "$source_path" ]; then
        echo "Error: 本地文件不存在: $source_path" >&2
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
        echo "Warn: 默认配置种子不存在，跳过: $seed_config"
        return 0
    fi

    if [ -f "$target_config" ]; then
        echo "运行配置已存在，跳过默认配置初始化: $target_config"
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
    echo "已初始化默认运行配置: $target_config"
}

seed_default_emoji_assets() {
    local seed_dir="${DEPLOY_ROOT}/holo-cortex-zero-main/default_workspace/emoji"
    local workspace_dir
    local emoji_dir
    local emoji_count
    local runtime_uid=${HCZ_RUNTIME_UID:-$(id -u)}
    local runtime_gid=${HCZ_RUNTIME_GID:-$(id -g)}

    if [ ! -d "$seed_dir" ]; then
        echo "Warn: 默认 emoji 种子目录不存在，跳过: $seed_dir"
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
        echo "已初始化默认 emoji 资源: $emoji_dir"
    else
        echo "emoji 目录已有 ${emoji_count} 个文件，跳过默认资源初始化: $emoji_dir"
    fi
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

# 解析命令行参数
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        cn|--cn)
            BUILD_REGION=cn
            shift
            ;;
        global|--global)
            BUILD_REGION=global
            shift
            ;;
        *)
            echo "未知选项: $1"
            echo "用法: $0 [cn|--cn|global|--global]"
            exit 1
            ;;
    esac
done

set_env_value() {
    local key=$1
    local value=$2
    if grep -q "^${key}=" .env; then
        sed -i "s|^${key}=.*|${key}=${value}|" .env
    else
        echo "${key}=${value}" >>.env
    fi
}

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
    echo "请选择使用的 Docker 安装源："
    echo "    1) Docker 官方"
    echo "    2) 阿里"
    echo "    3) Azure 中国云"

    read -r -p "请输入选项数字 (默认为 1): " num
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
            >&2 echo "未知选项，退出..."
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
        echo "Warn: 为避免冲突，Docker 官方安装脚本通常要求移除旧 Docker/容器运行时包。"
        if confirm_host_change "是否卸载 docker.io docker-doc docker-compose podman-docker containerd runc？" n; then
            for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do sudo apt-get remove "$pkg"; done
        else
            echo "已跳过卸载旧 Docker 包。若后续安装失败，请手动处理包冲突后重试。"
        fi
    fi
    if ! confirm_host_change "将从 https://get.docker.com 下载并执行 Docker 官方安装脚本，是否继续？" n; then
        echo "已跳过 Docker 官方安装脚本。"
        return 1
    fi
    echo "尝试获取 Docker 安装脚本..."
    while [ "$attempt_num" -le "$max_retries" ]; do
        if content=$(curl -fsSL -m 30 https://get.docker.com); then
            echo "Docker 安装脚本下载完成."
            # 使用 sed 命令修改 sleep 以取消等待
            if printf '%s\n' "$content" | sed 's#sleep#test#g' | sh -s -- --mirror "$mirror"; then
                DOCKER_COMPOSE_CMD="docker compose"
                return 0
            else
                echo "Docker 安装失败..." >&2
                return 1
            fi
        else
            if [ "$attempt_num" -eq "$max_retries" ]; then
                echo "Docker 安装脚本下载失败..." >&2
                return 1
            fi
            echo "Docker 安装脚本下载失败，正在重试($((attempt_num + 1))/$max_retries)"
            sleep 1
        fi
        attempt_num=$((attempt_num + 1))
    done
    return 1
}

# Docker 备用安装方式
install_docker_fallback() {
    if ! command -v apt-get &>/dev/null; then
        echo "包管理器非 apt，暂不支持..."
        return 1
    fi
    if ! confirm_host_change "将执行 apt-get update 并安装 docker.io docker-compose，是否继续？" n; then
        echo "已跳过 apt 备用安装。"
        return 1
    fi
    echo "正在更新软件源..."
    if ! sudo apt-get update; then
        echo "Error: 更新软件源失败，请检查您的网络连接。"
        return 1
    fi
    echo "正在安装 Docker..."
    if ! sudo apt-get install -y docker.io docker-compose; then
        echo "Error: Docker 安装失败，请检查您的网络连接或软件源配置。" >&2
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
        echo "Error: jq 未安装" >&2
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
            echo "Error: $daemon_file 文件内容有误。" >&2
            echo "请修复该文件或将其删除后重试。" >&2
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
                error("Error: daemon.json 中的 registry-mirrors 已存在但不是一个数组！请检查文件内容。")
        else
            .["registry-mirrors"] = ($new_mirrors_jq) + (.["registry-mirrors"] // [])
        end | .["registry-mirrors"] = ((.["registry-mirrors"] // []) | unique)'
    )

    # shellcheck disable=SC2181
    if [[ $? -ne 0 ]] || [[ -z "$updated_json" ]]; then
        echo "Error: jq 处理 JSON 失败。" >&2
        return 1
    fi

    if echo "$updated_json" | sudo tee "$daemon_file" > /dev/null; then
        return 0
    fi
    echo "Error: 写入 $daemon_file 文件失败。" >&2
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
    echo "HoloCortexZero 依赖于 Docker Compose，当前环境缺失。"
    echo "推荐专业部署用户先手动安装 Docker 与 Docker Compose；脚本也可辅助安装，但会修改宿主包状态。"
    if ! command -v apt-get &>/dev/null; then
        echo "Warn: 您可能需要手动卸载已安装的 docker"
    fi

    if ! confirm_host_change "是否让脚本辅助安装 Docker / Docker Compose？" n; then
        echo "已取消..." >&2
        exit 1
    fi
    echo "正在通过 Docker 官方安装脚本进行安装"
    select_docker_install_mirror
    if ! install_docker_via_official_script "$DOCKER_PKG_MIRROR"; then
        echo "Docker 安装失败..." >&2
        echo "正在尝试备用安装方式..."
        if ! install_docker_fallback; then
            echo "安装失败，退出..." >&2
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
echo "HCZ_DATA_DIR: $HCZ_DATA_DIR"

export HCZ_DATA_DIR=$HCZ_DATA_DIR

# 创建应用目录
ensure_hcz_data_dir || {
    echo "Error: 无法创建应用目录 $HCZ_DATA_DIR，请检查您的权限配置。"
    exit 1
}


# 进入部署根目录
cd "$DEPLOY_ROOT" || {
    echo "Error: 无法进入部署根目录 $DEPLOY_ROOT。"
    exit 1
}

# 如果当前目录没有 .env 文件，从部署根目录模板复制
if [ ! -f .env ]; then
    echo "未找到.env文件，正在复制根目录 .env.share.example..."
    if ! copy_local_file "${DEPLOY_ROOT}/.env.share.example" .env.share.example; then
        echo "Error: 无法复制根目录 .env.share.example，请检查部署包完整性。"
        exit 1
    fi
    if ! cp .env.share.example .env; then
        echo "Error: 无法将文件 .env.share.example 复制为 .env"
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
    echo "Error: 初始化默认运行配置失败。"
    exit 1
}

seed_default_emoji_assets || {
    echo "Error: 初始化默认 emoji 资源失败。"
    exit 1
}

if [ "$BUILD_REGION" = "cn" ]; then
    echo "已启用国内构建源配置（仅 docker build 使用，不进入运行态业务配置）。"
    set_env_value HCZ_NPM_REGISTRY "https://registry.npmmirror.com"
    set_env_value HCZ_UV_DEFAULT_INDEX "https://mirrors.aliyun.com/pypi/simple"
    set_env_value HCZ_APT_DEBIAN_MIRROR "http://mirrors.cloud.tencent.com/debian"
    set_env_value HCZ_APT_SECURITY_MIRROR "http://mirrors.cloud.tencent.com/debian-security"
    set_env_value HCZ_APT_NO_PROXY "true"
elif [ "$BUILD_REGION" = "global" ]; then
    echo "已启用默认国际构建源配置。"
    set_env_value HCZ_NPM_REGISTRY ""
    set_env_value HCZ_UV_DEFAULT_INDEX ""
    set_env_value HCZ_APT_DEBIAN_MIRROR ""
    set_env_value HCZ_APT_SECURITY_MIRROR ""
    set_env_value HCZ_APT_NO_PROXY ""
fi

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
    echo "Error: HCZ_EXPOSE_PORT 未在 .env 文件中设置"
    exit 1
fi
export HCZ_EXPOSE_PORT=$HCZ_EXPOSE_PORT

read -r -p "请检查并按需修改.env文件中的配置，未修改则按照默认配置安装，确认是否继续安装？[Y/n] " yn
echo ""
[ -z "$yn" ] && yn=y
if ! [[ "$yn" =~ ^[Yy]$ ]]; then
    echo -e "安装已取消..."
    exit 0
fi

# 添加 Docker 镜像到 daemon.json
if confirm_host_change "是否修改 /etc/docker/daemon.json 添加 Docker 镜像源？这可能影响宿主所有 Docker 拉镜像行为。" n; then
    if ! command -v jq &>/dev/null; then
        if command -v apt-get &>/dev/null; then
            if confirm_host_change "jq 未安装，将执行 apt-get update 并安装 jq，是否继续？" n; then
                sudo apt-get update && sudo apt-get install -y jq
            else
                echo "已跳过安装 jq，无法自动修改 Docker 镜像源。"
            fi
        else
            echo "包管理器非 apt，暂不支持..."
        fi
    fi
    if command -v jq &>/dev/null && add_docker_mirrors_prepend "${DOCKER_IMAGE_MIRRORS[@]}"; then
        if confirm_host_change "已写入 Docker daemon 配置，是否现在重载 systemd 并重启 Docker？这会影响宿主正在运行的容器。" n; then
            sudo systemctl daemon-reload
            sudo systemctl restart docker
        else
            echo "已跳过重启 Docker。请在合适窗口手动执行 systemctl daemon-reload && systemctl restart docker。"
        fi
    else
        echo "Error: 添加失败" >&2
    fi
fi

# 验证现行唯一部署入口
if [ ! -f docker-compose.yml ]; then
    echo "Error: 缺少根目录 docker-compose.yml，请从部署包根目录运行安装脚本。"
    exit 1
fi

# 本地构建主服务镜像
echo "正在本地构建 holo_cortex_zero 镜像..."
if ! sudo bash -c "cd \"$DEPLOY_ROOT\" && $DOCKER_COMPOSE_CMD --env-file .env -f docker-compose.yml build holo_cortex_zero"; then
    echo "Error: 无法本地构建 holo_cortex_zero 镜像，请检查 Dockerfile 与本地源码。"
    exit 1
fi

# 从.env文件加载环境变量
if [ -f .env ]; then
    echo "使用实例名称: ${INSTANCE_NAME}"
    echo "启动主服务中..."
    if ! sudo bash -c "cd \"$DEPLOY_ROOT\" && $DOCKER_COMPOSE_CMD --env-file .env -f docker-compose.yml up -d"; then
        echo "Error: 无法启动主服务，请检查 Docker Compose 配置。"
        exit 1
    fi
else
    echo "Error: .env 文件不存在"
    exit 1
fi

# 旧独立运行时已退役：这里不再拉取、不再构建相关镜像。
echo "检测到旧独立运行时已退役，跳过相关镜像处理。"

# 放行防火墙端口
echo "HoloCortexZero 主服务需放行端口 ${HCZ_EXPOSE_PORT:-20261}/tcp..."
if command -v ufw &>/dev/null; then
    if confirm_host_change "是否通过 ufw 放行 ${HCZ_EXPOSE_PORT:-20261}/tcp？这会修改宿主防火墙规则。" n; then
        echo -e "\n正在配置防火墙..."
        if ! sudo ufw allow "${HCZ_EXPOSE_PORT:-20261}/tcp"; then
            echo "Warning: 无法放行防火墙端口 ${HCZ_EXPOSE_PORT:-20261}，如服务访问受限，请检查防火墙设置。"
        fi
    else
        echo "已跳过 ufw 防火墙配置。若服务访问受限，请手动放行 ${HCZ_EXPOSE_PORT:-20261}/tcp。"
    fi
fi

echo -e "\n=== 部署完成！==="
echo "你可以通过以下命令查看服务日志："
echo "  HoloCortexZero: 'sudo docker logs -f ${INSTANCE_NAME}holo_cortex_zero'"
echo "  NapCat: 'sudo docker logs -f ${INSTANCE_NAME}hcz_napcat'"

# 显示重要的配置信息
echo -e "\n=== 重要配置信息 ==="
ONEBOT_ACCESS_TOKEN=$(grep -m1 '^ONEBOT_ACCESS_TOKEN=' .env | cut -d '=' -f2-)
HCZ_ADMIN_PASSWORD=$(grep -m1 '^HCZ_ADMIN_PASSWORD=' .env | cut -d '=' -f2-)
HCZ_ADMIN_USERNAME=$(grep -m1 '^HCZ_ADMIN_USERNAME=' .env | cut -d '=' -f2-)
HCZ_ADMIN_USERNAME=${HCZ_ADMIN_USERNAME:-admin}
QDRANT_API_KEY=$(grep -m1 '^QDRANT_API_KEY=' .env | cut -d '=' -f2-)
echo "OneBot 访问令牌: ${ONEBOT_ACCESS_TOKEN}"
echo "管理员账号: ${HCZ_ADMIN_USERNAME} | 密码: ${HCZ_ADMIN_PASSWORD}"

echo -e "\n=== 服务访问信息 ==="
echo "HoloCortexZero 主服务端口: ${HCZ_EXPOSE_PORT:-20261}"
echo "HoloCortexZero Web 访问地址: http://127.0.0.1:${HCZ_EXPOSE_PORT:-20261}"
echo "NapCat WebUI 访问地址: http://127.0.0.1:${HCZ_EXPOSE_PORT:-20261}/napcat/webui/"

echo -e "\n=== 注意事项 ==="
echo "1. 如果您使用的是云服务器，请在云服务商控制台的安全组中放行以下端口："
echo "   - ${HCZ_EXPOSE_PORT:-20261}/tcp (HoloCortexZero 主服务)"
echo "2. NapCat WebUI 默认通过 HCZ /napcat 内置反代访问，不需要单独开放 NapCat 端口"
echo "3. 如果需要从外部访问，请将上述地址中的 127.0.0.1 替换为您的服务器公网IP"
echo "4. 请使用 'sudo docker logs ${INSTANCE_NAME}hcz_napcat' 查看机器人 QQ 账号二维码进行登录"

echo -e "\n安装完成！祝您使用愉快！"
