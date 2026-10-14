#!/usr/bin/env bash
# ==============================================================================
# 织网 (WebWeaver) - Ubuntu / Debian 一键原生部署脚�?# 适用环境: Ubuntu 20.04 / 22.04 / 24.04, Debian 11 / 12
# 无需 Docker，全自动配置 Python 3 虚拟环境、编译前端、设�?ICMP �?Systemd 守护
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================================${NC}"
echo -e "${GREEN}      织网 (WebWeaver) 自动化原生部署程�?           ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. 检�?root 权限
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[错误] 请使�?root 用户�?sudo 执行此脚本：${NC}"
    echo -e "例如: sudo bash $0"
    exit 1
fi

INSTALL_DIR="/opt/webweaver"
REPO_URL="https://github.com/langdalebecks204-bit/webweaver.git"

# 2. 安装系统基础依赖
echo -e "\n${YELLOW}[1/7] 更新系统包并安装基础工具...${NC}"
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl ca-certificates libcap2-bin

# 3. 检查并安装 Node.js (需�?>= 18)
echo -e "\n${YELLOW}[2/7] 检�?Node.js 环境...${NC}"
NEED_NODE_INSTALL=true
if command -v node >/dev/null 2>&1; then
    NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        echo -e "${GREEN}检测到 Node.js $(node -v)，符合要求�?{NC}"
        NEED_NODE_INSTALL=false
    fi
fi

if [ "$NEED_NODE_INSTALL" = true ]; then
    echo -e "${BLUE}正在安装 Node.js 20 LTS...${NC}"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
    echo -e "${GREEN}Node.js $(node -v) 安装完成�?{NC}"
fi

# 4. 准备项目代码
echo -e "\n${YELLOW}[3/7] 准备 WebWeaver 源码...${NC}"
CURRENT_DIR=$(pwd)
if [ -f "$CURRENT_DIR/backend/requirements.txt" ] && [ -f "$CURRENT_DIR/frontend/package.json" ]; then
    echo -e "${GREEN}检测到当前目录下已有项目源码，同步�?$INSTALL_DIR...${NC}"
    mkdir -p "$INSTALL_DIR"
    cp -r "$CURRENT_DIR"/* "$INSTALL_DIR"/ 2>/dev/null || true
    cp -r "$CURRENT_DIR"/.[!.]* "$INSTALL_DIR"/ 2>/dev/null || true
else
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo -e "${BLUE}$INSTALL_DIR 已存在，拉取最新代�?..${NC}"
        cd "$INSTALL_DIR" && git pull || true
    else
        echo -e "${BLUE}克隆仓库代码�?$INSTALL_DIR...${NC}"
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
fi

# 5. 编译前端静态页�?echo -e "\n${YELLOW}[4/7] 编译前端静态资�?(可能需�?1~2 分钟)...${NC}"
cd "$INSTALL_DIR/frontend"
npm install --no-audit --prefer-offline
npm run build
if [ ! -d "$INSTALL_DIR/frontend/dist" ]; then
    echo -e "${RED}[错误] 前端构建失败，未生成 frontend/dist 目录�?{NC}"
    exit 1
fi
echo -e "${GREEN}前端构建成功�?{NC}"

# 6. 配置后端 Python 运行环境
echo -e "\n${YELLOW}[5/7] 配置后端 Python 虚拟环境与依�?..${NC}"
cd "$INSTALL_DIR/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 创建数据存储目录
mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/data/uploads"

# 7. 配置环境文件与权�?echo -e "\n${YELLOW}[6/7] 配置环境变量与网络特�?..${NC}"
ENV_FILE="$INSTALL_DIR/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    RANDOM_JWT=$(openssl rand -hex 16 2>/dev/null || echo "webweaver-$(date +%s)-jwt-key")
    cat << EOF > "$ENV_FILE"
# 织网运行配置
WEAVER_DB_URL=sqlite:///$INSTALL_DIR/data/weaver.db
WEAVER_UPLOAD_DIR=$INSTALL_DIR/data/uploads
WEAVER_FRONTEND_DIR=$INSTALL_DIR/frontend/dist
WEAVER_JWT_SECRET=$RANDOM_JWT
WEAVER_DEFAULT_ADMIN_PASSWORD=admin123
WEAVER_POLL_INTERVAL_MINUTES=5
EOF
    echo -e "${GREEN}已自动生成配置文件：$ENV_FILE${NC}"
fi

# 开�?ICMP Ping 权限（核心）
sysctl -w net.ipv4.ping_group_range="0 2147483647" >/dev/null 2>&1 || true
echo 'net.ipv4.ping_group_range = 0 2147483647' > /etc/sysctl.d/99-webweaver.conf
sysctl --system >/dev/null 2>&1 || true
setcap cap_net_raw+ep $(readlink -f "$INSTALL_DIR/backend/.venv/bin/python3") 2>/dev/null || true

# 8. 注册并启�?Systemd 服务
echo -e "\n${YELLOW}[7/7] 注册开机自启动 Systemd 服务...${NC}"
SERVICE_FILE="/etc/systemd/system/webweaver.service"
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=WebWeaver Network Monitoring Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/backend
EnvironmentFile=$INSTALL_DIR/backend/.env
ExecStart=$INSTALL_DIR/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
AmbientCapabilities=CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now webweaver

# 9. 检查服务运行状态并获取本机 IP
sleep 2
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="127.0.0.1"
fi

echo -e "\n${BLUE}======================================================${NC}"
if systemctl is-active --quiet webweaver; then
    echo -e "${GREEN}🎉 恭喜！WebWeaver 已成功安装并启动�?{NC}"
    echo -e "访问地址: ${YELLOW}http://${SERVER_IP}:8000${NC}"
    echo -e "默认账号: ${GREEN}admin${NC}"
    echo -e "默认密码: ${GREEN}admin123${NC} (请在登录后及时修�?"
    echo -e "${BLUE}======================================================${NC}"
    echo -e "常用管理命令�?
    echo -e "  查看运行状�? ${YELLOW}systemctl status webweaver${NC}"
    echo -e "  查看实时日志: ${YELLOW}journalctl -u webweaver -f${NC}"
    echo -e "  重启服务    : ${YELLOW}systemctl restart webweaver${NC}"
    echo -e "  停止服务    : ${YELLOW}systemctl stop webweaver${NC}"
    echo -e "  数据存储目录: ${YELLOW}$INSTALL_DIR/data${NC}"
else
    echo -e "${RED}⚠️ 服务安装完成，但启动状态异常�?{NC}"
    echo -e "请使用以下命令查看具体错误日志："
    echo -e "${YELLOW}journalctl -u webweaver -n 50 --no-pager${NC}"
fi
echo -e "${BLUE}======================================================${NC}"
