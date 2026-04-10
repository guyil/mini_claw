#!/usr/bin/env bash
#
# Mini Claw Platform 一键启动脚本
# 启动后端 (FastAPI :8000) 和前端 (Next.js :3000)
# 自动检测端口占用并释放

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
BACKEND_PORT=8000
FRONTEND_PORT=3000

# ── 颜色 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 端口清理 ──────────────────────────────────────────
kill_port() {
    local port=$1
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        log_warn "端口 $port 被占用 (PID: $(echo $pids | tr '\n' ' '))，正在终止..."
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
        # 二次确认
        pids=$(lsof -ti :"$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            log_error "无法释放端口 $port，请手动处理"
            exit 1
        fi
        log_ok "端口 $port 已释放"
    else
        log_ok "端口 $port 空闲"
    fi
}

# ── 依赖检查 ──────────────────────────────────────────
check_deps() {
    local missing=()
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    command -v node    >/dev/null 2>&1 || missing+=("node")
    command -v npm     >/dev/null 2>&1 || missing+=("npm")

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "缺少依赖: ${missing[*]}"
        exit 1
    fi
}

# ── 清理函数 (Ctrl+C 时同时停止前后端) ────────────────
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    log_info "正在停止服务..."
    [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null && log_ok "后端已停止"
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && log_ok "前端已停止"
    wait 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# ── 主流程 ────────────────────────────────────────────
main() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Mini Claw Platform 一键启动            ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
    echo ""

    check_deps

    # 0) 检查 venv
    if [ ! -f "$PYTHON" ]; then
        log_error "未找到 venv，请先运行: ./scripts/init-dev.sh"
        exit 1
    fi
    log_ok "使用 venv: $($PYTHON --version)"

    # 1) 释放端口
    log_info "检查端口占用..."
    kill_port $BACKEND_PORT
    kill_port $FRONTEND_PORT

    # 2) 安装/检查前端依赖
    if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
        log_info "安装前端依赖..."
        (cd "$PROJECT_DIR/frontend" && npm install --silent)
        log_ok "前端依赖安装完成"
    fi

    # 3) 启动后端 (使用 venv Python)
    log_info "启动后端 (FastAPI :$BACKEND_PORT)..."
    (
        cd "$BACKEND_DIR"
        "$PYTHON" -m uvicorn app.main:app --reload --port $BACKEND_PORT 2>&1 \
            | while IFS= read -r line; do echo -e "${BLUE}[后端]${NC} $line"; done
    ) &
    BACKEND_PID=$!

    # 等待后端就绪
    log_info "等待后端就绪..."
    for i in $(seq 1 30); do
        if curl -sf "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1; then
            log_ok "后端已就绪"
            break
        fi
        if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
            log_error "后端启动失败，请检查日志"
            exit 1
        fi
        sleep 1
    done

    # 4) 启动前端
    log_info "启动前端 (Next.js :$FRONTEND_PORT)..."
    (
        cd "$PROJECT_DIR/frontend"
        npm run dev 2>&1 \
            | while IFS= read -r line; do echo -e "${YELLOW}[前端]${NC} $line"; done
    ) &
    FRONTEND_PID=$!

    # 等待前端就绪
    log_info "等待前端就绪..."
    for i in $(seq 1 30); do
        if curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
            log_ok "前端已就绪"
            break
        fi
        if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
            log_error "前端启动失败，请检查日志"
            exit 1
        fi
        sleep 1
    done

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════${NC}"
    echo -e "  后端: ${BLUE}http://localhost:$BACKEND_PORT${NC}  (API docs: /docs)"
    echo -e "  前端: ${BLUE}http://localhost:$FRONTEND_PORT${NC}"
    echo -e "  按 ${RED}Ctrl+C${NC} 停止所有服务"
    echo -e "${GREEN}════════════════════════════════════════════${NC}"
    echo ""

    # 保持脚本运行，等待子进程
    wait
}

main "$@"
