#!/usr/bin/env bash
# VideoFetcher 启动脚本
# 使用方式: ./run.sh 或 bash run.sh

set -e

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "=========================================="
echo "  VideoFetcher"
echo "=========================================="

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

# 确保目录存在
mkdir -p downloads logs

# 读取端口
PORT=$(grep -E "^\s+port:" config.yaml | head -1 | awk '{print $2}')
PORT=${PORT:-7860}

printf "${GREEN}启动服务...${NC}\n"
echo "访问地址: http://localhost:${PORT}"
echo "按 Ctrl+C 停止服务"
echo ""

# 激活虚拟环境并启动
source .venv/bin/activate

# 让本地请求绑过代理（解决 Gradio 启动时的代理问题）
export no_proxy="localhost,127.0.0.1,0.0.0.0"
export NO_PROXY="localhost,127.0.0.1,0.0.0.0"

python app.py
