#!/bin/bash

# 生产环境启动脚本
# 使用Gunicorn + Uvicorn Workers 部署FastAPI应用

set -euo pipefail

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
LOG_DIR="${ROOT_DIR}/logs"
PID_DIR="${ROOT_DIR}/pids"

# 创建必要目录
mkdir -p "${LOG_DIR}" "${PID_DIR}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 生产环境配置
export WORKERS=${WORKERS:-4}
export WORKER_CONNECTIONS=${WORKER_CONNECTIONS:-1000}
export MAX_REQUESTS=${MAX_REQUESTS:-1000}
export TIMEOUT=${TIMEOUT:-30}
export REDIS_MAX_CONNECTIONS=${REDIS_MAX_CONNECTIONS:-20}
export CACHE_MAX_SIZE=${CACHE_MAX_SIZE:-5000}
export VECTOR_STORE_CACHE_SIZE=${VECTOR_STORE_CACHE_SIZE:-50}
export RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE:-60}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# 检查依赖
check_dependencies() {
    info "检查系统依赖..."
    
    # 检查Python
    if ! command -v python3 >/dev/null 2>&1; then
        error "Python3 未安装"
        exit 1
    fi
    
    # 检查Node.js
    if ! command -v node >/dev/null 2>&1; then
        error "Node.js 未安装"
        exit 1
    fi
    
    # 检查Redis
    if ! command -v redis-cli >/dev/null 2>&1; then
        warn "Redis CLI 未安装，请确保Redis服务可用"
    fi
    
    success "依赖检查完成"
}

# 检查端口占用
check_port() {
    local port=$1
    local service_name=$2
    
    if lsof -i :${port} >/dev/null 2>&1; then
        warn "端口 ${port} 已被占用 (${service_name})"
        info "尝试释放端口..."
        
        # 获取占用端口的进程ID
        local pid=$(lsof -ti :${port})
        if [[ -n "${pid}" ]]; then
            kill -TERM ${pid} 2>/dev/null || true
            sleep 2
            
            # 如果进程仍在运行，强制杀死
            if kill -0 ${pid} 2>/dev/null; then
                kill -KILL ${pid} 2>/dev/null || true
                sleep 1
            fi
        fi
        
        success "端口 ${port} 已释放"
    fi
}

# 启动医生端后端 (生产模式)
start_doctor_backend_prod() {
    info "启动医生端后端服务 (生产模式, 端口8000)..."
    
    cd "${ROOT_DIR}/backend"
    
    # 检查虚拟环境
    if [[ ! -d ".venv" ]]; then
        info "创建后端虚拟环境..."
        python3 -m venv .venv
    fi
    
    # 激活虚拟环境并安装依赖
    source .venv/bin/activate
    
    # 安装生产依赖
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt >/dev/null 2>&1
    fi
    
    # 安装Gunicorn
    pip install gunicorn >/dev/null 2>&1
    
    # 检查端口
    check_port 8000 "医生端后端"
    
    # 启动Gunicorn
    gunicorn app:app \
        --workers ${WORKERS} \
        --worker-class uvicorn.workers.UvicornWorker \
        --worker-connections ${WORKER_CONNECTIONS} \
        --max-requests ${MAX_REQUESTS} \
        --max-requests-jitter 100 \
        --timeout ${TIMEOUT} \
        --keepalive 5 \
        --bind 0.0.0.0:8000 \
        --pid "${PID_DIR}/doctor_backend.pid" \
        --access-logfile "${LOG_DIR}/doctor_backend_access.log" \
        --error-logfile "${LOG_DIR}/doctor_backend_error.log" \
        --log-level ${LOG_LEVEL,,} \
        --preload \
        --daemon
    
    success "医生端后端已启动 (生产模式, 端口: 8000, Workers: ${WORKERS})"
}

# 启动患者端后端 (生产模式)
start_patient_backend_prod() {
    info "启动患者端后端服务 (生产模式, 端口8001)..."
    
    cd "${ROOT_DIR}/backend/patient"
    
    # 检查虚拟环境
    if [[ ! -d ".venv" ]]; then
        info "创建患者端后端虚拟环境..."
        python3 -m venv .venv
    fi
    
    # 激活虚拟环境并安装依赖
    source .venv/bin/activate
    
    # 安装生产依赖
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt >/dev/null 2>&1
    fi
    
    # 安装Gunicorn
    pip install gunicorn >/dev/null 2>&1
    
    # 检查端口
    check_port 8001 "患者端后端"
    
    # 启动Gunicorn
    gunicorn app:app \
        --workers ${WORKERS} \
        --worker-class uvicorn.workers.UvicornWorker \
        --worker-connections ${WORKER_CONNECTIONS} \
        --max-requests ${MAX_REQUESTS} \
        --max-requests-jitter 100 \
        --timeout ${TIMEOUT} \
        --keepalive 5 \
        --bind 0.0.0.0:8001 \
        --pid "${PID_DIR}/patient_backend.pid" \
        --access-logfile "${LOG_DIR}/patient_backend_access.log" \
        --error-logfile "${LOG_DIR}/patient_backend_error.log" \
        --log-level ${LOG_LEVEL,,} \
        --preload \
        --daemon
    
    success "患者端后端已启动 (生产模式, 端口: 8001, Workers: ${WORKERS})"
}

# 启动医生端前端 (生产构建)
start_doctor_frontend_prod() {
    info "启动医生端前端服务 (生产模式, 端口3000)..."
    
    cd "${ROOT_DIR}/frontend"
    
    # 检查Node.js依赖
    if [[ ! -d "node_modules" ]]; then
        info "安装前端依赖..."
        npm install >/dev/null 2>&1
    fi
    
    # 设置环境变量指向医生端后端
    export NEXT_PUBLIC_API_BASE_URL="http://localhost:8000/api/v1"
    
    # 检查端口
    check_port 3000 "医生端前端"
    
    # 构建生产版本
    info "构建生产版本..."
    npm run build >/dev/null 2>&1
    
    # 启动生产服务器
    nohup npm start > "${LOG_DIR}/doctor_frontend.log" 2>&1 &
    local pid=$!
    echo $pid > "${PID_DIR}/doctor_frontend.pid"
    
    success "医生端前端已启动 (生产模式, PID: $pid, 端口: 3000)"
}

# 启动患者端前端 (生产构建)
start_patient_frontend_prod() {
    info "启动患者端前端服务 (生产模式, 端口3001)..."
    
    cd "${ROOT_DIR}/patient"
    
    # 检查Node.js依赖
    if [[ ! -d "node_modules" ]]; then
        info "安装患者端前端依赖..."
        npm install >/dev/null 2>&1
    fi
    
    # 设置环境变量指向患者端后端
    export NEXT_PUBLIC_API_BASE_URL="http://localhost:8001/api/v1"
    export PORT=3001
    
    # 检查端口
    check_port 3001 "患者端前端"
    
    # 构建生产版本
    info "构建生产版本..."
    npm run build >/dev/null 2>&1
    
    # 启动生产服务器
    nohup npm start > "${LOG_DIR}/patient_frontend.log" 2>&1 &
    local pid=$!
    echo $pid > "${PID_DIR}/patient_frontend.pid"
    
    success "患者端前端已启动 (生产模式, PID: $pid, 端口: 3001)"
}

# 等待服务启动
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    info "等待 ${service_name} 启动..."
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -s "http://localhost:${port}/health" >/dev/null 2>&1 || \
           curl -s "http://localhost:${port}/" >/dev/null 2>&1; then
            success "${service_name} 已就绪"
            return 0
        fi
        
        sleep 2
        ((attempt++))
    done
    
    warn "${service_name} 启动超时，请检查日志"
    return 1
}

# 检查服务状态
check_services_status() {
    info "检查服务状态..."
    
    local services=(
        "8000:医生端后端"
        "8001:患者端后端"
        "3000:医生端前端"
        "3001:患者端前端"
    )
    
    for service in "${services[@]}"; do
        local port="${service%%:*}"
        local name="${service##*:}"
        
        if curl -s "http://localhost:${port}/" >/dev/null 2>&1; then
            success "${name} (端口${port}): ✅ 运行中"
        else
            warn "${name} (端口${port}): ❌ 未响应"
        fi
    done
}

# 显示服务信息
show_service_info() {
    echo ""
    echo "🚀 生产环境服务已启动"
    echo "=================================="
    echo "医生端:"
    echo "  - 后端: http://localhost:8000 (Workers: ${WORKERS})"
    echo "  - 前端: http://localhost:3000"
    echo ""
    echo "患者端:"
    echo "  - 后端: http://localhost:8001 (Workers: ${WORKERS})"
    echo "  - 前端: http://localhost:3001"
    echo ""
    echo "日志文件:"
    echo "  - ${LOG_DIR}/"
    echo ""
    echo "PID文件:"
    echo "  - ${PID_DIR}/"
    echo ""
    echo "停止服务: ./stop_production.sh"
    echo "查看状态: ./check_production_status.sh"
}

# 主函数
main() {
    info "启动生产环境服务..."
    
    # 检查依赖
    check_dependencies
    
    # 启动后端服务
    start_doctor_backend_prod
    start_patient_backend_prod
    
    # 等待后端服务启动
    wait_for_service 8000 "医生端后端"
    wait_for_service 8001 "患者端后端"
    
    # 启动前端服务
    start_doctor_frontend_prod
    start_patient_frontend_prod
    
    # 等待前端服务启动
    wait_for_service 3000 "医生端前端"
    wait_for_service 3001 "患者端前端"
    
    # 检查服务状态
    sleep 5
    check_services_status
    
    # 显示服务信息
    show_service_info
    
    success "所有服务已启动完成！"
}

# 执行主函数
main "$@"