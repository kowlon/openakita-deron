#!/bin/bash
#
# OpenAkita 服务管理脚本
# 用法: ./scripts/servers.sh {start|stop|restart|status}
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 配置
BACKEND_HOST="127.0.0.1"
BACKEND_PORT=18900
FRONTEND_PORT=5175
PID_DIR="$PROJECT_ROOT/.pids"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
LOG_DIR="$PROJECT_ROOT/logs/servers"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# 确保目录存在
mkdir -p "$PID_DIR" "$LOG_DIR"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -i ":$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

# 获取监听端口的进程 PID
get_port_pid() {
    local port=$1
    lsof -i ":$port" -sTCP:LISTEN -t 2>/dev/null | head -1
}

# 等待端口可用
wait_for_port_free() {
    local port=$1
    local timeout=${2:-30}
    local elapsed=0
    while check_port "$port" && [ $elapsed -lt $timeout ]; do
        sleep 1
        ((elapsed++))
    done
    if check_port "$port"; then
        return 1
    fi
    return 0
}

# 等待端口启动
wait_for_port_ready() {
    local port=$1
    local timeout=${2:-30}
    local elapsed=0
    while ! check_port "$port" && [ $elapsed -lt $timeout ]; do
        sleep 1
        ((elapsed++))
    done
    if check_port "$port"; then
        return 0
    fi
    return 1
}

# 启动后端服务
start_backend() {
    log_step "启动后端服务..."

    if check_port $BACKEND_PORT; then
        log_warn "后端端口 $BACKEND_PORT 已被占用"
        local existing_pid=$(get_port_pid $BACKEND_PORT)
        if [ -n "$existing_pid" ]; then
            log_warn "现有进程 PID: $existing_pid"
        fi
        return 1
    fi

    # 激活虚拟环境并启动
    source "$PROJECT_ROOT/venv/bin/activate"

    # 后台启动
    nohup python -m openakita serve > "$BACKEND_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$BACKEND_PID_FILE"

    # 等待启动
    if wait_for_port_ready $BACKEND_PORT 30; then
        log_info "后端服务已启动 (PID: $pid)"
        log_info "后端地址: http://$BACKEND_HOST:$BACKEND_PORT"
        return 0
    else
        log_error "后端服务启动超时"
        if [ -f "$BACKEND_LOG" ]; then
            log_error "日志内容:"
            tail -20 "$BACKEND_LOG" >&2
        fi
        return 1
    fi
}

# 启动前端服务
start_frontend() {
    log_step "启动前端服务..."

    if check_port $FRONTEND_PORT; then
        log_warn "前端端口 $FRONTEND_PORT 已被占用"
        local existing_pid=$(get_port_pid $FRONTEND_PORT)
        if [ -n "$existing_pid" ]; then
            log_warn "现有进程 PID: $existing_pid"
        fi
        return 1
    fi

    cd "$PROJECT_ROOT/webapps/seeagent-webui"

    # 后台启动
    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$FRONTEND_PID_FILE"

    # 等待启动
    if wait_for_port_ready $FRONTEND_PORT 30; then
        log_info "前端服务已启动 (PID: $pid)"
        log_info "前端地址: http://localhost:$FRONTEND_PORT"
        cd "$PROJECT_ROOT"
        return 0
    else
        log_error "前端服务启动超时"
        if [ -f "$FRONTEND_LOG" ]; then
            log_error "日志内容:"
            tail -20 "$FRONTEND_LOG" >&2
        fi
        cd "$PROJECT_ROOT"
        return 1
    fi
}

# 停止后端服务
stop_backend() {
    log_step "停止后端服务..."

    local pid=""
    if [ -f "$BACKEND_PID_FILE" ]; then
        pid=$(cat "$BACKEND_PID_FILE")
    fi

    # 通过端口查找进程
    local port_pid=$(get_port_pid $BACKEND_PORT)

    if [ -n "$port_pid" ]; then
        pid="$port_pid"
    fi

    if [ -z "$pid" ]; then
        log_warn "后端服务未运行"
        rm -f "$BACKEND_PID_FILE"
        return 0
    fi

    # 发送 SIGTERM
    kill $pid 2>/dev/null || true

    # 等待进程结束
    local elapsed=0
    while kill -0 $pid 2>/dev/null && [ $elapsed -lt 10 ]; do
        sleep 1
        ((elapsed++))
    done

    # 如果进程还在，强制杀掉
    if kill -0 $pid 2>/dev/null; then
        log_warn "后端服务未响应，强制终止..."
        kill -9 $pid 2>/dev/null || true
        wait_for_port_free $BACKEND_PORT 5 || true
    fi

    rm -f "$BACKEND_PID_FILE"
    log_info "后端服务已停止"
}

# 停止前端服务
stop_frontend() {
    log_step "停止前端服务..."

    local pid=""
    if [ -f "$FRONTEND_PID_FILE" ]; then
        pid=$(cat "$FRONTEND_PID_FILE")
    fi

    # 通过端口查找进程
    local port_pid=$(get_port_pid $FRONTEND_PORT)

    if [ -n "$port_pid" ]; then
        pid="$port_pid"
    fi

    if [ -z "$pid" ]; then
        log_warn "前端服务未运行"
        rm -f "$FRONTEND_PID_FILE"
        return 0
    fi

    # 发送 SIGTERM
    kill $pid 2>/dev/null || true

    # 等待进程结束
    local elapsed=0
    while kill -0 $pid 2>/dev/null && [ $elapsed -lt 10 ]; do
        sleep 1
        ((elapsed++))
    done

    # 如果进程还在，强制杀掉
    if kill -0 $pid 2>/dev/null; then
        log_warn "前端服务未响应，强制终止..."
        kill -9 $pid 2>/dev/null || true
        wait_for_port_free $FRONTEND_PORT 5 || true
    fi

    rm -f "$FRONTEND_PID_FILE"
    log_info "前端服务已停止"
}

# 查看服务状态
show_status() {
    echo ""
    echo "==================================="
    echo "     OpenAkita 服务状态"
    echo "==================================="
    echo ""

    # 后端状态
    echo -e "${BLUE}[后端服务]${NC}"
    if check_port $BACKEND_PORT; then
        local pid=$(get_port_pid $BACKEND_PORT)
        echo -e "  状态: ${GREEN}运行中${NC}"
        echo -e "  PID:  $pid"
        echo -e "  地址: http://$BACKEND_HOST:$BACKEND_PORT"

        # 健康检查
        local health=$(curl -s "http://$BACKEND_HOST:$BACKEND_PORT/" 2>/dev/null)
        if [ -n "$health" ]; then
            echo -e "  健康: ${GREEN}正常${NC}"
        else
            echo -e "  健康: ${YELLOW}无响应${NC}"
        fi
    else
        echo -e "  状态: ${RED}未运行${NC}"
    fi
    echo ""

    # 前端状态
    echo -e "${BLUE}[前端服务]${NC}"
    if check_port $FRONTEND_PORT; then
        local pid=$(get_port_pid $FRONTEND_PORT)
        echo -e "  状态: ${GREEN}运行中${NC}"
        echo -e "  PID:  $pid"
        echo -e "  地址: http://localhost:$FRONTEND_PORT"
    else
        echo -e "  状态: ${RED}未运行${NC}"
    fi
    echo ""

    echo "==================================="
    echo "日志目录: $LOG_DIR"
    echo "==================================="
}

# 启动所有服务
start_all() {
    log_info "启动所有服务..."
    start_backend
    start_frontend
    log_info "所有服务启动完成"
    show_status
}

# 停止所有服务
stop_all() {
    log_info "停止所有服务..."
    stop_frontend
    stop_backend
    log_info "所有服务已停止"
}

# 重启所有服务
restart_all() {
    log_info "重启所有服务..."
    stop_all
    sleep 2
    start_all
}

# 显示帮助
show_help() {
    echo ""
    echo "OpenAkita 服务管理脚本"
    echo ""
    echo "用法: $0 {start|stop|restart|status|help}"
    echo ""
    echo "命令:"
    echo "  start   启动所有服务 (后端 + 前端)"
    echo "  stop    停止所有服务"
    echo "  restart 重启所有服务"
    echo "  status  查看服务状态"
    echo "  help    显示帮助信息"
    echo ""
    echo "单独操作:"
    echo "  $0 start backend   仅启动后端"
    echo "  $0 start frontend  仅启动前端"
    echo "  $0 stop backend    仅停止后端"
    echo "  $0 stop frontend   仅停止前端"
    echo ""
}

# 主入口
case "${1:-}" in
    start)
        case "${2:-}" in
            backend)
                start_backend
                ;;
            frontend)
                start_frontend
                ;;
            *)
                start_all
                ;;
        esac
        ;;
    stop)
        case "${2:-}" in
            backend)
                stop_backend
                ;;
            frontend)
                stop_frontend
                ;;
            *)
                stop_all
                ;;
        esac
        ;;
    restart)
        restart_all
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac