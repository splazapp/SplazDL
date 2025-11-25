#!/usr/bin/env bash
# VideoFetcher 后台启动脚本
# 使用方式: ./nohup-run.sh [start|stop|status|restart]

set -e

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 配置
PID_FILE="$PROJECT_DIR/logs/app.pid"
LOG_FILE="$PROJECT_DIR/logs/app.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

# 确保日志目录存在
mkdir -p logs downloads

# 获取进程状态
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

# 启动服务
start() {
    if is_running; then
        printf "${YELLOW}⚠ 服务已在运行中 (PID: $(get_pid))${NC}\n"
        exit 1
    fi

    # 检查虚拟环境
    if [ ! -d ".venv" ]; then
        printf "${RED}✗ 虚拟环境不存在，请先运行 ./setup.sh${NC}\n"
        exit 1
    fi

    # 检查配置文件
    if [ ! -f "config.yaml" ]; then
        printf "${RED}✗ 配置文件不存在，请先运行 ./setup.sh${NC}\n"
        exit 1
    fi

    # 读取端口
    PORT=$(grep -E "^\s+port:" config.yaml | head -1 | awk '{print $2}')
    PORT=${PORT:-7860}

    printf "${GREEN}启动后台服务...${NC}\n"

    # 激活虚拟环境并后台启动
    source .venv/bin/activate

    # 设置代理绕过
    export no_proxy="localhost,127.0.0.1,0.0.0.0"
    export NO_PROXY="localhost,127.0.0.1,0.0.0.0"

    # 后台启动，日志输出到文件
    nohup python app.py >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    sleep 1

    if is_running; then
        printf "${GREEN}✓ 服务已启动 (PID: $(get_pid))${NC}\n"
        echo "访问地址: http://localhost:${PORT}"
        echo "日志文件: $LOG_FILE"
    else
        printf "${RED}✗ 服务启动失败，请查看日志: $LOG_FILE${NC}\n"
        exit 1
    fi
}

# 停止服务
stop() {
    if ! is_running; then
        printf "${YELLOW}⚠ 服务未运行${NC}\n"
        rm -f "$PID_FILE"
        return 0
    fi

    local pid=$(get_pid)
    printf "${GREEN}停止服务 (PID: $pid)...${NC}\n"
    kill "$pid" 2>/dev/null

    # 等待进程退出
    local count=0
    while is_running && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if is_running; then
        printf "${YELLOW}强制终止进程...${NC}\n"
        kill -9 "$pid" 2>/dev/null
    fi

    rm -f "$PID_FILE"
    printf "${GREEN}✓ 服务已停止${NC}\n"
}

# 查看状态
status() {
    if is_running; then
        printf "${GREEN}✓ 服务运行中 (PID: $(get_pid))${NC}\n"
    else
        printf "${YELLOW}○ 服务未运行${NC}\n"
    fi
}

# 重启服务
restart() {
    stop
    sleep 1
    start
}

# 查看日志
logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        printf "${YELLOW}日志文件不存在${NC}\n"
    fi
}

# 主入口
case "${1:-start}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    *)
        echo "用法: $0 {start|stop|status|restart|logs}"
        echo ""
        echo "命令说明:"
        echo "  start   - 后台启动服务"
        echo "  stop    - 停止服务"
        echo "  status  - 查看服务状态"
        echo "  restart - 重启服务"
        echo "  logs    - 查看实时日志"
        exit 1
        ;;
esac
