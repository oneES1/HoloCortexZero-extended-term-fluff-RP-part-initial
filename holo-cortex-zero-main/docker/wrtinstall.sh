#!/bin/ash

# 默认不使用 napcat
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DEPLOY_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
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

    if [ "$default" = "y" ] || [ "$default" = "Y" ]; then
        read -r -p "$prompt [Y/n] " yn
        [ -z "$yn" ] && yn=y
    else
        read -r -p "$prompt [y/N] " yn
        [ -z "$yn" ] && yn=n
    fi
    echo ""
    [ "$yn" = "y" ] || [ "$yn" = "Y" ]
}

# 解析命令行参数
if [ "$#" -gt 0 ]; then
    echo "未知选项: $1"
    exit 1
fi

# 生成随机字符串的函数（兼容软路由环境）
generate_random_string() {
    local length=$1
    # 多种方法尝试生成随机字符串
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -base64 $((length * 2)) | tr -dc 'a-zA-Z0-9' | head -c "$length"
    elif [ -c /dev/urandom ]; then
        dd if=/dev/urandom bs=1 count=$((length * 2)) 2>/dev/null | tr -dc 'a-zA-Z0-9' | head -c "$length"
    else
        # 最后备选方案：使用日期和随机数
        date +%s%N | md5sum | head -c "$length"
    fi
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

# 安装 Docker Compose
install_docker_compose() {
    echo "正在安装 Docker Compose..."
    if ! confirm_host_change "将安装 Docker Compose，可能修改 OpenWrt 包状态或写入 /usr/local/bin/docker-compose，是否继续？" n; then
        echo "已跳过 Docker Compose 安装。"
        return 1
    fi
    
    # 首先尝试通过 opkg 安装
    if command -v opkg >/dev/null 2>&1; then
        if confirm_host_change "是否执行 opkg update && opkg install docker-compose？" n; then
            echo "通过 opkg 安装 Docker Compose..."
            opkg update
            if opkg install docker-compose; then
                echo "✓ Docker Compose 安装成功"
                DOCKER_COMPOSE_CMD="docker-compose"
                return 0
            else
                echo "opkg 安装失败，尝试其他方法..."
            fi
        fi
    fi
    
    # 如果 opkg 安装失败，尝试下载二进制文件
    if ! confirm_host_change "是否访问 GitHub release 并下载 Docker Compose 二进制文件？" n; then
        echo "已跳过 Docker Compose 二进制下载。"
        return 1
    fi
    echo "通过二进制文件安装 Docker Compose..."
    
    # 检测系统架构
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64)
            arch="x86_64"
            ;;
        aarch64)
            arch="aarch64"
            ;;
        armv7l)
            arch="armv7"
            ;;
        *)
            echo "不支持的架构: $arch"
            return 1
            ;;
    esac
    
    # 固定已验证版本，避免每次安装都去查询 GitHub latest。
    local version="v2.27.1"

    # 下载 Docker Compose
    local download_url="https://github.com/docker/compose/releases/download/${version}/docker-compose-linux-${arch}"
    
    echo "下载 Docker Compose ${version} for ${arch}..."
    if wget -q -O /usr/local/bin/docker-compose "$download_url"; then
        chmod +x /usr/local/bin/docker-compose
        DOCKER_COMPOSE_CMD="docker-compose"
        echo "✓ Docker Compose 安装成功"
        return 0
    else
        echo "✗ Docker Compose 下载失败"
        return 1
    fi
}

# 检查 Docker 环境
check_docker_environment() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "错误: Docker 未安装"
        echo "iStoreOS 应该自带 Docker，请检查系统是否正常"
        exit 1
    fi
    
    # 检查 docker compose 功能
    if docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
        echo "✓ 使用 Docker Compose Plugin"
    elif command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker-compose"
        echo "✓ 使用 Docker Compose Standalone"
    else
        echo "Docker Compose 未安装。推荐专业部署用户先手动安装；脚本可辅助安装，但会修改宿主环境。"
        if install_docker_compose; then
            echo "✓ Docker Compose 安装完成"
        else
            echo "错误: Docker Compose 安装失败"
            echo "请手动安装 Docker Compose 后重试"
            exit 1
        fi
    fi
}

# 检查 Docker 存储空间
check_docker_space() {
    echo "检查 Docker 存储空间..."
    
    # 获取当前 Docker 根目录
    local docker_root
    docker_root=$(docker info 2>/dev/null | grep "Docker Root Dir" | cut -d ':' -f2 | tr -d ' ' || echo "/overlay/upper/opt/docker")
    
    # 检查可用空间（以KB为单位）
    local available_kb
    if [ -d "$docker_root" ]; then
        available_kb=$(df "$docker_root" 2>/dev/null | awk 'NR==2 {print $4}' | grep -E '^[0-9]+$' || echo "0")
    else
        available_kb="0"
    fi
    
    # 转换为 MB 和 GB
    local available_mb=$((available_kb / 1024))
    local available_gb=$((available_mb / 1024))
    
    echo "当前 Docker 目录: $docker_root"
    echo "可用空间: ${available_gb}GB (${available_mb}MB)"
    
    # 如果小于 3GB，发出警告并退出
    if [ "$available_mb" -lt 3072 ]; then  # 3GB in MB
        echo ""
        echo "⚠️  警告: Docker 根目录可用空间不足 (小于 3GB)"
        echo "HoloCortexZero 需要较多存储空间，建议先迁移 Docker 目录到更大的存储空间"
        echo "安装已取消，请先迁移 Docker 目录后再运行安装脚本"
        exit 1
    fi
}

# 检查防火墙规则是否存在 - 原子性检查
check_firewall_rule_exists() {
    local rule_name=$1
    local dest_port=$2
    
    # 原子性检查：确保名称和端口在同一个规则中
    # 使用 awk 处理 uci 输出，确保名称和端口来自同一个规则段
    uci show firewall | awk -v rule_name="$rule_name" -v dest_port="$dest_port" '
    /^firewall\.@rule\[[0-9]+\]\.name=/ {
        current_name = substr($0, index($0, "=")+2)
        gsub(/\x27/, "", current_name)  # 移除单引号
        name_matched = (current_name == rule_name)
    }
    /^firewall\.@rule\[[0-9]+\]\.dest_port=/ {
        current_port = substr($0, index($0, "=")+2)
        gsub(/\x27/, "", current_port)  # 移除单引号
        port_matched = (current_port == dest_port)
        
        # 如果当前规则同时匹配名称和端口，则成功
        if (name_matched && port_matched) {
            found = 1
            exit 0
        }
        
        # 重置匹配状态，准备下一个规则
        name_matched = 0
        port_matched = 0
    }
    END {
        exit !found
    }' >/dev/null 2>&1
    
    return $?
}

# 初始化变量
DOCKER_COMPOSE_CMD=""

# 检查 Docker 环境
echo "检查 Docker 环境..."
check_docker_environment

# 检查 Docker 存储空间
check_docker_space

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
    echo "生成 POSTGRES_PASSWORD..."
    POSTGRES_PASSWORD=$(generate_random_string 32)
    if [ -z "$POSTGRES_PASSWORD" ]; then
        echo "Error: 无法生成随机字符串 POSTGRES_PASSWORD"
        exit 1
    fi
    set_env_value POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
fi

HCZ_ADMIN_PASSWORD=$(grep -m1 '^HCZ_ADMIN_PASSWORD=' .env | cut -d '=' -f2-)
if is_weak_admin_password "$HCZ_ADMIN_PASSWORD"; then
    echo "生成 HCZ_ADMIN_PASSWORD..."
    HCZ_ADMIN_PASSWORD=$(generate_random_string 32)
    if [ -z "$HCZ_ADMIN_PASSWORD" ]; then
        echo "Error: 无法生成随机字符串 HCZ_ADMIN_PASSWORD"
        exit 1
    fi
    set_env_value HCZ_ADMIN_PASSWORD "$HCZ_ADMIN_PASSWORD"
fi

QDRANT_API_KEY=$(grep -m1 '^QDRANT_API_KEY=' .env | cut -d '=' -f2-)
if [ -z "$QDRANT_API_KEY" ]; then
    echo "生成 QDRANT_API_KEY..."
    QDRANT_API_KEY=$(generate_random_string 32)
    if [ -z "$QDRANT_API_KEY" ]; then
        echo "Error: 无法生成随机字符串 QDRANT_API_KEY"
        exit 1
    fi
    set_env_value QDRANT_API_KEY "$QDRANT_API_KEY"
fi

# 从.env文件加载环境变量
INSTANCE_NAME=$(grep -m1 '^INSTANCE_NAME=' .env | cut -d '=' -f2)
export INSTANCE_NAME=${INSTANCE_NAME:-""}

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
if ! echo "$yn" | grep -q "^[Yy]"; then
    echo -e "安装已取消..."
    exit 0
fi

if [ ! -f docker-compose.yml ]; then
    echo "Error: 缺少根目录 docker-compose.yml，请从部署包根目录运行安装脚本。"
    exit 1
fi

# 本地构建主服务镜像
echo "正在本地构建 holo_cortex_zero 镜像..."
if ! (cd "$DEPLOY_ROOT" && $DOCKER_COMPOSE_CMD --env-file .env -f docker-compose.yml build holo_cortex_zero); then
    echo "Error: 无法本地构建 holo_cortex_zero 镜像，请检查 Dockerfile 与本地源码。"
    exit 1
fi

# 从.env文件加载环境变量
if [ -f .env ]; then
    echo "使用实例名称: ${INSTANCE_NAME}"
    echo "启动主服务中..."
    if ! (cd "$DEPLOY_ROOT" && $DOCKER_COMPOSE_CMD --env-file .env -f docker-compose.yml up -d); then
        echo "Error: 无法启动主服务，请检查 Docker Compose 配置。"
        exit 1
    fi
else
    echo "Error: .env 文件不存在"
    exit 1
fi

# 旧独立运行时已退役：这里不再拉取、不再构建相关镜像。
echo "检测到旧独立运行时已退役，跳过相关镜像处理。"

# 配置防火墙（使用 OpenWrt 的 uci 命令）
echo "HoloCortexZero 主服务需放行端口 ${HCZ_EXPOSE_PORT:-20261}/tcp..."

if command -v uci >/dev/null 2>&1; then
    echo "正在配置防火墙..."
    
    # HoloCortexZero 防火墙规则
    if ! check_firewall_rule_exists "HoloCortexZero" "${HCZ_EXPOSE_PORT:-20261}"; then
        uci add firewall rule
        uci set firewall.@rule[-1].name="HoloCortexZero"
        uci set firewall.@rule[-1].src="wan"
        uci set firewall.@rule[-1].proto="tcp"
        uci set firewall.@rule[-1].dest_port="${HCZ_EXPOSE_PORT:-20261}"
        uci set firewall.@rule[-1].target="ACCEPT"
        echo "已添加 HoloCortexZero 防火墙规则"
    else
        echo "HoloCortexZero 防火墙规则已存在"
    fi

    if confirm_host_change "是否提交防火墙配置并重启 firewall 服务？这会影响当前网络连接。" n; then
        uci commit firewall
        echo "重启防火墙服务..."
        /etc/init.d/firewall restart >/dev/null 2>&1 && echo "防火墙重启完成"
    else
        echo "已跳过提交和重启防火墙。请在合适窗口手动执行 uci commit firewall && /etc/init.d/firewall restart。"
    fi
fi

# 获取局域网IP地址
get_lan_ip() {
    # 尝试多种方法获取局域网IP
    local ip
    ip=$(ip addr show | grep -E 'inet (192\.168|10\.|172\.1[6789]|172\.2[0-9]|172\.3[01])' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d'/' -f1)
    
    if [ -z "$ip" ]; then
        ip=$(ifconfig | grep -E 'inet (addr:)?(192\.168|10\.|172\.1[6789]|172\.2[0-9]|172\.3[01])' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d':' -f2)
    fi
    
    echo "$ip"
}

LAN_IP=$(get_lan_ip)

# 显示 Docker 存储信息
echo "=== Docker 存储信息 ==="
docker_root=$(docker info 2>/dev/null | grep "Docker Root Dir" | cut -d ':' -f2 | tr -d ' ' || echo "未知")
echo "Docker 根目录: $docker_root"

# 显示存储使用情况
echo "存储使用情况:"
df -h "$docker_root" 2>/dev/null || echo "无法获取存储信息"

echo "=== 部署完成！==="

# 显示重要的配置信息
echo "=== 重要配置信息 ==="
ONEBOT_ACCESS_TOKEN=$(grep -m1 '^ONEBOT_ACCESS_TOKEN=' .env | cut -d '=' -f2-)
HCZ_ADMIN_PASSWORD=$(grep -m1 '^HCZ_ADMIN_PASSWORD=' .env | cut -d '=' -f2-)
HCZ_ADMIN_USERNAME=$(grep -m1 '^HCZ_ADMIN_USERNAME=' .env | cut -d '=' -f2-)
HCZ_ADMIN_USERNAME=${HCZ_ADMIN_USERNAME:-admin}
echo "OneBot 访问令牌: ${ONEBOT_ACCESS_TOKEN}"
echo "管理员账号: ${HCZ_ADMIN_USERNAME} | 密码: ${HCZ_ADMIN_PASSWORD}"

echo "=== 服务访问信息 ==="
echo "HoloCortexZero 主服务端口: ${HCZ_EXPOSE_PORT:-20261}"
echo "HoloCortexZero Web 本地访问地址: http://127.0.0.1:${HCZ_EXPOSE_PORT:-20261}"

# 显示局域网访问地址
if [ -n "$LAN_IP" ]; then
    echo "HoloCortexZero Web 局域网访问地址: http://${LAN_IP}:${HCZ_EXPOSE_PORT:-20261}"
else
    echo "HoloCortexZero Web 局域网访问地址: 请使用路由器IP替换127.0.0.1"
fi

echo "NapCat WebUI 本地地址: http://127.0.0.1:${HCZ_EXPOSE_PORT:-20261}/napcat/webui/"
if [ -n "$LAN_IP" ]; then
    echo "NapCat WebUI 局域网访问地址: http://${LAN_IP}:${HCZ_EXPOSE_PORT:-20261}/napcat/webui/"
else
    echo "NapCat WebUI 局域网访问地址: 请使用路由器IP替换127.0.0.1"
fi

echo "=== 注意事项 ==="
echo "1. 软路由防火墙规则已自动配置"
echo "2. 如果需要从外部访问，请将上述地址中的 127.0.0.1 替换为您的路由器IP"
echo "3. 应用数据存储在: $HCZ_DATA_DIR"

echo "安装完成！祝您使用愉快！"
