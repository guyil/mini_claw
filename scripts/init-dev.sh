#!/usr/bin/env bash
#
# Mini Claw Platform 开发环境初始化
# 启动 PG + Redis → 运行数据库迁移 → 构建 CLI 沙箱镜像

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 检查 Docker ──────────────────────────────────────
check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker 未安装，请先安装 Docker Desktop"
        exit 1
    fi
    if ! docker info >/dev/null 2>&1; then
        log_warn "Docker daemon 未运行，尝试启动 Docker Desktop..."
        open -a Docker 2>/dev/null || true
        for i in $(seq 1 30); do
            docker info >/dev/null 2>&1 && break
            [ "$i" -eq 30 ] && { log_error "Docker 启动超时，请手动启动"; exit 1; }
            sleep 3
        done
    fi
    log_ok "Docker 已就绪"
}

# ── 主流程 ────────────────────────────────────────────
main() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Mini Claw Platform 开发环境初始化       ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
    echo ""

    check_docker

    # 1) 启动 PostgreSQL + Redis
    log_info "启动 PostgreSQL + Redis..."
    cd "$PROJECT_DIR"
    docker compose up -d
    log_ok "数据库服务已启动"

    # 等待 PostgreSQL 就绪
    log_info "等待 PostgreSQL 就绪..."
    for i in $(seq 1 30); do
        docker compose exec -T postgres pg_isready -U mclaw >/dev/null 2>&1 && break
        [ "$i" -eq 30 ] && { log_error "PostgreSQL 启动超时"; exit 1; }
        sleep 2
    done
    log_ok "PostgreSQL 已就绪"

    # 2) 安装后端依赖
    log_info "安装后端 Python 依赖..."
    cd "$PROJECT_DIR/backend"
    python3 -m pip install -e ".[dev]" --quiet 2>/dev/null || python3 -m pip install -e ".[dev]"
    log_ok "后端依赖已安装"

    # 3) 运行数据库迁移
    log_info "运行数据库迁移 (Alembic)..."
    cd "$PROJECT_DIR/backend"
    python3 -m alembic upgrade head
    log_ok "数据库迁移完成"

    # 4) 构建 CLI 沙箱镜像
    log_info "构建 CLI 沙箱 Docker 镜像..."
    cd "$PROJECT_DIR"
    docker build -t mclaw-sandbox:latest -f sandbox/Dockerfile sandbox/
    log_ok "沙箱镜像构建完成"

    # 5) 安装前端依赖
    if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
        log_info "安装前端依赖..."
        cd "$PROJECT_DIR/frontend"
        npm install --silent
        log_ok "前端依赖已安装"
    else
        log_ok "前端依赖已存在"
    fi

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════${NC}"
    echo -e "  初始化完成！"
    echo ""
    echo -e "  启动服务:  ${BLUE}./scripts/start.sh${NC}"
    echo -e "  运行测试:  ${BLUE}cd backend && python3 -m pytest tests/ -v${NC}"
    echo -e "${GREEN}════════════════════════════════════════════${NC}"
    echo ""
}

main "$@"
