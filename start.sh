#!/usr/bin/env bash
# P01_fapiao_helper 启动脚本
# 双击或 ./start.sh 运行：自动准备 venv、安装依赖、启动服务并打开浏览器到 http://127.0.0.1:5000
set -e

# 切换到脚本所在目录（项目根）
cd "$(dirname "$0")"

VENV=".venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
REQ="requirements.txt"
URL="http://127.0.0.1:5000"
MARKER="$VENV/.deps_installed"

# 1. 创建虚拟环境
if [ ! -x "$PYTHON" ]; then
    echo "[1/4] 创建虚拟环境 .venv ..."
    if ! command -v python3 >/dev/null 2>&1; then
        echo "错误：未找到 python3，请先安装 Python 3.9+ 并加入 PATH。"
        exit 1
    fi
    python3 -m venv "$VENV"
fi

# 2. 安装依赖（首次或 requirements.txt 更新时）
if [ ! -f "$MARKER" ] || [ "$REQ" -nt "$MARKER" ]; then
    echo "[2/4] 安装依赖（首次较慢，含 PaddleOCR 模型约 200MB）..."
    "$PIP" install --upgrade pip
    "$PIP" install -r "$REQ"
    touch "$MARKER"
else
    echo "[2/4] 依赖已就绪，跳过安装。"
fi

# 3. 延迟打开浏览器（后台，不阻塞服务启动）
echo "[3/4] 准备打开浏览器 $URL ..."
(
    sleep 2
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
        open "$URL" >/dev/null 2>&1 || true
    else
        echo "    未检测到浏览器打开命令，请手动访问 $URL"
    fi
) &

# 4. 启动 Flask 服务（python -m fapiao_helper）
echo "[4/4] 启动服务（按 Ctrl+C 退出）..."
echo "----------------------------------------"
"$PYTHON" -m fapiao_helper
