# SplazDL / VideoFetcher - just 命令
# 使用: just <recipe> 或 just 直接启动服务

# 虚拟环境与解释器
venv := ".venv"
python := venv + "/bin/python"
pip := venv + "/bin/pip"

# 默认：启动服务（前台）
default:
    @just run

# 安装：完整环境（虚拟环境 + 依赖 + 配置 + 目录）
setup:
    ./setup.sh

# 运行：前台启动 Web 服务
run:
    [ -d .venv ] || (echo "请先执行: just setup" && exit 1)
    [ -f config.yaml ] || (echo "请先执行: just setup" && exit 1)
    mkdir -p downloads logs
    no_proxy="localhost,127.0.0.1,0.0.0.0" NO_PROXY="localhost,127.0.0.1,0.0.0.0" {{python}} app.py

# 后台启动服务
start:
    ./nohup-run.sh start

# 停止后台服务
stop:
    ./nohup-run.sh stop

# 查看后台服务状态
status:
    ./nohup-run.sh status

# 重启后台服务
restart:
    ./nohup-run.sh restart

# 实时查看应用日志
logs:
    ./nohup-run.sh logs

# 安装/更新依赖（不执行完整 setup）
install:
    {{pip}} install -r requirements.txt

# 安装依赖（使用 uv，与 setup 一致）
install-uv:
    . .venv/bin/activate && uv pip install -r requirements.txt

# 从示例创建配置文件（若不存在）
config:
    [[ -f config.yaml ]] && echo "config.yaml 已存在" || (cp config.example.yaml config.yaml && echo "已创建 config.yaml")

# 运行所有测试
test:
    {{python}} test_url_preprocessing.py
    {{python}} test_cookies.py

# 代码检查（若已安装 ruff）
lint:
    {{venv}}/bin/ruff check . 2>/dev/null || true
    {{venv}}/bin/ruff format --check . 2>/dev/null || true

# 格式化代码
fmt:
    {{venv}}/bin/ruff format . 2>/dev/null || true
    {{venv}}/bin/ruff check --fix . 2>/dev/null || true

# 列出所有可用命令
list:
    just --list
