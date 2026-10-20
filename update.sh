#!/usr/bin/env bash
# ==============================================================================
# 织网 (WebWeaver) - 源码部署服务器一键 / 自动更新脚本
# 支持手动更新与 Crontab 定时无人值守自动更新
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 1. 检查 root 权限
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[错误] 请使用 root 用户或 sudo 执行此脚本：${NC}"
    echo -e "例如: sudo bash $0"
    exit 1
fi

# 2. 定位部署目录
INSTALL_DIR="/opt/webweaver"
CURRENT_DIR=$(cd "$(dirname "$0")" && pwd)

if [ -d "$CURRENT_DIR/backend" ] && [ -d "$CURRENT_DIR/.git" ]; then
    TARGET_DIR="$CURRENT_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
    TARGET_DIR="$INSTALL_DIR"
else
    echo -e "${RED}[错误] 未找到 WebWeaver 源码部署目录 ($INSTALL_DIR 或当前目录)。${NC}"
    exit 1
fi

# 3. 处理 Crontab 定时自动更新安装 / 卸载参数
if [ "$1" = "--cron" ]; then
    CRON_CMD="0 3 * * * /bin/bash $TARGET_DIR/update.sh > /var/log/webweaver-autoupdate.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "$TARGET_DIR/update.sh" ; echo "$CRON_CMD") | crontab -
    echo -e "${GREEN}✓ 已成功设置 Crontab 定时任务！每天凌晨 03:00 将自动拉取 Git 最新代码并热更新。${NC}"
    echo -e "日志文件: /var/log/webweaver-autoupdate.log"
    exit 0
elif [ "$1" = "--remove-cron" ]; then
    crontab -l 2>/dev/null | grep -v "$TARGET_DIR/update.sh" | crontab -
    echo -e "${GREEN}✓ 已移除 Crontab 定时自动更新任务。${NC}"
    exit 0
fi

echo -e "${BLUE}======================================================${NC}"
echo -e "${GREEN}         织网 (WebWeaver) 服务更新程序                ${NC}"
echo -e "${BLUE}======================================================${NC}"
echo -e "目标目录: ${YELLOW}$TARGET_DIR${NC}"

cd "$TARGET_DIR"

# 4. 自动备份当前数据库与配置（安全双保险）
echo -e "\n${YELLOW}[1/5] 执行数据安全快照备份...${NC}"
BACKUP_DIR="$TARGET_DIR/data/backups"
mkdir -p "$BACKUP_DIR"

# 优先从 .env 读取实际数据库路径，缺省使用 $TARGET_DIR/data/weaver.db
DB_FILE="$TARGET_DIR/data/weaver.db"
if [ -f "$TARGET_DIR/backend/.env" ]; then
    CUSTOM_DB=$(grep -E "^WEAVER_DB_URL=" "$TARGET_DIR/backend/.env" | cut -d'=' -f2 | sed 's|sqlite:///||')
    if [ -n "$CUSTOM_DB" ] && [ -f "$CUSTOM_DB" ]; then
        DB_FILE="$CUSTOM_DB"
    fi
fi

if [ -f "$DB_FILE" ]; then
    BACKUP_NAME="weaver.db.pre_update_$(date +%Y%m%d_%H%M%S)"
    cp "$DB_FILE" "$BACKUP_DIR/$BACKUP_NAME"
    echo -e "${GREEN}✓ 已自动备份数据库至: $BACKUP_DIR/$BACKUP_NAME${NC}"
    # 仅保留最近 15 份预更新备份，防止占满磁盘
    ls -t "$BACKUP_DIR"/weaver.db.pre_update_* 2>/dev/null | tail -n +16 | xargs rm -f 2>/dev/null || true
else
    echo -e "${YELLOW}未发现已有数据库文件 ($DB_FILE)，跳过备份。${NC}"
fi

# 5. 拉取 Git 最新代码
echo -e "\n${YELLOW}[2/5] 从 GitHub 远程仓库拉取最新代码...${NC}"
git fetch --all
BEFORE_COMMIT=$(git rev-parse HEAD)
git reset --hard origin/main
AFTER_COMMIT=$(git rev-parse HEAD)

if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
    echo -e "${GREEN}当前已是最新代码 ($AFTER_COMMIT)。${NC}"
else
    echo -e "${GREEN}代码更新成功: ${BEFORE_COMMIT:0:7} -> ${AFTER_COMMIT:0:7}${NC}"
fi

# 6. 更新后端 Python 依赖
echo -e "\n${YELLOW}[3/5] 检查并更新后端 Python 依赖...${NC}"
if [ -d "$TARGET_DIR/backend/.venv" ]; then
    "$TARGET_DIR/backend/.venv/bin/pip" install --upgrade pip -q
    "$TARGET_DIR/backend/.venv/bin/pip" install -r "$TARGET_DIR/backend/requirements.txt" -q
    # 确保 ping 权限 (setcap)
    PYTHON_BIN=$(readlink -f "$TARGET_DIR/backend/.venv/bin/python3" || true)
    if [ -n "$PYTHON_BIN" ]; then
        setcap cap_net_raw+ep "$PYTHON_BIN" 2>/dev/null || true
    fi
else
    echo -e "${YELLOW}未检测到 backend/.venv，跳过 pip 依赖检查。${NC}"
fi

# 7. 编译 / 更新前端静态资源
echo -e "\n${YELLOW}[4/5] 检查前端资源...${NC}"
if command -v npm >/dev/null 2>&1 && [ -d "$TARGET_DIR/frontend" ]; then
    echo -e "${BLUE}检测到 Node/npm 环境，正在构建前端 dist...${NC}"
    cd "$TARGET_DIR/frontend"
    npm install --no-audit --prefer-offline -q
    npm run build -q
    cd "$TARGET_DIR"
else
    echo -e "${YELLOW}未安装 Node/npm，跳过前端现场编译，保留现有静态页面。${NC}"
fi

# 8. 重启 systemd 服务
echo -e "\n${YELLOW}[5/5] 平滑重启 WebWeaver 服务...${NC}"
if systemctl list-unit-files | grep -q "webweaver.service"; then
    systemctl daemon-reload
    systemctl restart webweaver
    sleep 2
    if systemctl is-active --quiet webweaver; then
        echo -e "${GREEN}✓ WebWeaver 服务重启成功，当前正在平稳运行！${NC}"
    else
        echo -e "${RED}⚠️ 服务重启后状态异常，请查看日志：journalctl -u webweaver -n 30 --no-pager${NC}"
    fi
else
    echo -e "${YELLOW}未检测到 systemd 服务 webweaver，请手动重启你的主进程。${NC}"
fi

echo -e "\n${BLUE}======================================================${NC}"
echo -e "${GREEN}🎉 更新流程全部完成！${NC}"
echo -e "${BLUE}======================================================${NC}"
