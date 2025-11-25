#!/usr/bin/env bash
# VideoFetcher 安装脚本
# 使用方式: ./setup.sh 或 bash setup.sh

set -e

echo "=========================================="
echo "  VideoFetcher 安装脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 检查 uv
printf "\n${YELLOW}[1/5] 检查 uv...${NC}\n"
if command -v uv &> /dev/null; then
    printf "${GREEN}✓ uv 已安装${NC}\n"
else
    echo "安装 uv..."
    pip install uv -q
    printf "${GREEN}✓ uv 安装完成${NC}\n"
fi

# 检查 FFmpeg
printf "\n${YELLOW}[2/5] 检查 FFmpeg...${NC}\n"
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version | head -n1)
    printf "${GREEN}✓ $FFMPEG_VERSION${NC}\n"
else
    printf "${RED}✗ 未找到 FFmpeg${NC}\n"
    echo "请安装 FFmpeg:"
    echo "  macOS: brew install ffmpeg"
    echo "  Ubuntu: sudo apt install ffmpeg"
    exit 1
fi

# 创建虚拟环境
printf "\n${YELLOW}[3/5] 创建虚拟环境...${NC}\n"
if [ -d ".venv" ]; then
    echo "虚拟环境已存在，跳过创建"
else
    uv venv .venv --python 3.12
    printf "${GREEN}✓ 虚拟环境创建成功${NC}\n"
fi

# 安装依赖
printf "\n${YELLOW}[4/5] 安装依赖...${NC}\n"
source .venv/bin/activate
uv pip install -r requirements.txt
printf "${GREEN}✓ 依赖安装完成${NC}\n"

# 创建配置文件
printf "\n${YELLOW}[5/5] 初始化配置...${NC}\n"
if [ -f "config.yaml" ]; then
    echo "配置文件已存在，跳过创建"
else
    cp config.example.yaml config.yaml
    printf "${GREEN}✓ 已创建 config.yaml（请修改默认密码）${NC}\n"
fi

# 创建必要目录
mkdir -p downloads logs

printf "\n${GREEN}==========================================\n"
echo "  安装完成！"
printf "==========================================${NC}\n"
echo ""
echo "后续步骤:"
echo "  1. 编辑 config.yaml 修改用户密码"
echo "  2. 运行 ./run.sh 启动服务"
echo ""
