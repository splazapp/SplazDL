# SplazDL - just 命令
# 使用: just 或 just <recipe>，例如 just run、just start、just config

pid_file := "logs/app.pid"
log_file := "logs/app.log"

# 默认：前台运行
default:
    @just run

# 前台启动 Web 服务
run:
    [ -f config.yaml ] || (echo "✗ 请先执行: just config" && exit 1)
    mkdir -p downloads logs
    no_proxy="localhost,127.0.0.1,0.0.0.0" NO_PROXY="localhost,127.0.0.1,0.0.0.0" python3 app.py

# 初始化：检查 FFmpeg、创建 config 与目录
setup:
    #!/usr/bin/env bash
    set -e
    echo "=========================================="
    echo "  SplazDL 初始化"
    echo "=========================================="
    command -v ffmpeg &>/dev/null || { echo "✗ 未找到 FFmpeg，请安装: brew install ffmpeg"; exit 1; }
    echo "✓ FFmpeg 已安装"
    if [ -f config.yaml ]; then
      echo "config.yaml 已存在，跳过"
    else
      cp config.example.yaml config.yaml
      echo "✓ 已创建 config.yaml（请修改默认密码）"
    fi
    mkdir -p downloads logs
    echo "✓ 目录已创建"
    echo ""
    echo "后续: pip install -r requirements.txt && just run"

# 从示例创建配置文件（若不存在）
config:
    [[ -f config.yaml ]] && echo "config.yaml 已存在" || (cp config.example.yaml config.yaml && echo "已创建 config.yaml")

# 后台启动服务
start:
    #!/usr/bin/env bash
    set -e
    mkdir -p logs downloads
    [ -f config.yaml ] || { echo "✗ 请先执行: just config"; exit 1; }
    PORT=$(grep -E "^\s+port:" config.yaml | head -1 | awk '{print $2}')
    PORT=${PORT:-7860}
    if [ -f "{{pid_file}}" ]; then
      pid=$(cat "{{pid_file}}")
      if kill -0 "$pid" 2>/dev/null; then
        echo "⚠ 服务已在运行 (PID: $pid)"
        exit 1
      fi
    fi
    echo "启动后台服务..."
    no_proxy="localhost,127.0.0.1,0.0.0.0" NO_PROXY="localhost,127.0.0.1,0.0.0.0" nohup python3 app.py >> "{{log_file}}" 2>&1 &
    echo $! > "{{pid_file}}"
    sleep 1
    if kill -0 $(cat "{{pid_file}}") 2>/dev/null; then
      echo "✓ 服务已启动 (PID: $(cat {{pid_file}}))"
      echo "访问: http://localhost:${PORT}"
      echo "日志: {{log_file}}"
    else
      echo "✗ 启动失败，请查看 {{log_file}}"
      exit 1
    fi

# 停止后台服务
stop:
    #!/usr/bin/env bash
    set -e
    if [ ! -f "{{pid_file}}" ]; then
      echo "○ 服务未运行"
      rm -f "{{pid_file}}"
      exit 0
    fi
    pid=$(cat "{{pid_file}}")
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "○ 服务未运行"
      rm -f "{{pid_file}}"
      exit 0
    fi
    echo "停止服务 (PID: $pid)..."
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "强制终止..."
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "{{pid_file}}"
    echo "✓ 服务已停止"

# 查看后台服务状态
status:
    #!/usr/bin/env bash
    if [ -f "{{pid_file}}" ] && kill -0 $(cat "{{pid_file}}") 2>/dev/null; then
      echo "✓ 服务运行中 (PID: $(cat {{pid_file}}))"
    else
      echo "○ 服务未运行"
    fi

# 重启后台服务
restart:
    just stop
    sleep 1
    just start

# 实时查看应用日志
logs:
    [ -f "{{log_file}}" ] && tail -f "{{log_file}}" || echo "日志文件不存在"

# 运行测试
test:
    python3 test_url_preprocessing.py
    python3 test_cookies.py

# 代码检查（需安装 ruff）
lint:
    ruff check . 2>/dev/null || true
    ruff format --check . 2>/dev/null || true

# 格式化代码
fmt:
    ruff format . 2>/dev/null || true
    ruff check --fix . 2>/dev/null || true

# 列出所有命令
list:
    just --list
