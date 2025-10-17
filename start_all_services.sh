#!/usr/bin/env bash
set -euo pipefail

# RAG医疗系统 - 全服务启动脚本
# 医生端: 后端8000, 前端3000
# 患者端: 后端8001, 前端3001

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }

# 检查并关闭端口占用
kill_port() {
    local port=$1
    local service_name=$2
    
    info "检查端口 ${port} (${service_name})"
    
    if command -v lsof >/dev/null 2>&1; then
        local pids=$(lsof -ti tcp:${port} 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            warn "端口 ${port} 被占用，正在关闭进程: $pids"
            echo "$pids" | xargs kill -9 2>/dev/null || true
            sleep 2
            
            # 再次检查
            local remaining_pids=$(lsof -ti tcp:${port} 2>/dev/null || true)
            if [[ -n "$remaining_pids" ]]; then
                error "无法关闭端口 ${port} 的进程: $remaining_pids"
                return 1
            else
                success "端口 ${port} 已释放"
            fi
        else
            info "端口 ${port} 未被占用"
        fi
    else
        warn "lsof 命令不可用，跳过端口检查"
    fi
}

# 检查依赖
check_dependencies() {
    info "检查系统依赖..."
    
    # 检查 Python
    if ! command -v python3 >/dev/null 2>&1; then
        error "Python3 未安装"
        exit 1
    fi
    
    # 检查 Node.js
    if ! command -v node >/dev/null 2>&1; then
        error "Node.js 未安装"
        exit 1
    fi
    
    # 检查 npm
    if ! command -v npm >/dev/null 2>&1; then
        error "npm 未安装"
        exit 1
    fi
    
    success "系统依赖检查完成"
}

# 设置Python虚拟环境
setup_python_env() {
    info "设置Python虚拟环境..."
    
    cd "${ROOT_DIR}"
    
    # 检查虚拟环境
    if [[ ! -d ".venv" ]]; then
        info "创建Python虚拟环境..."
        python3 -m venv .venv
    fi
    
    # 激活虚拟环境
    source .venv/bin/activate
    
    # 安装依赖
    if [[ -f "requirements.txt" ]]; then
        info "安装Python依赖..."
        pip install -r requirements.txt
    fi
    
    success "Python环境设置完成"
}

# 设置前端依赖
setup_frontend_deps() {
    info "设置前端依赖..."
    
    cd "${ROOT_DIR}/frontend"
    
    if [[ ! -d "node_modules" ]]; then
        info "安装前端依赖..."
        npm install
    fi
    
    success "前端依赖设置完成"
}

# 启动医生端后端 (8000)
start_doctor_backend() {
    info "启动医生端后端服务 (端口8000)..."
    
    cd "${ROOT_DIR}/backend"
    
    # 检查虚拟环境
    if [[ ! -d ".venv" ]]; then
        info "创建后端虚拟环境..."
        python3 -m venv .venv
    fi
    
    # 激活虚拟环境并安装依赖
    source .venv/bin/activate
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt >/dev/null 2>&1
    fi
    
    # 启动服务
    nohup uvicorn app:app --host 0.0.0.0 --port 8000 --reload > ../logs/doctor_backend.log 2>&1 &
    local pid=$!
    echo $pid > ../logs/doctor_backend.pid
    
    success "医生端后端已启动 (PID: $pid, 端口: 8000)"
}

# 启动患者端后端 (8001)
start_patient_backend() {
    info "启动患者端后端服务 (端口8001)..."
    
    cd "${ROOT_DIR}/backend/patient"
    
    # 检查虚拟环境
    if [[ ! -d ".venv" ]]; then
        info "创建患者端后端虚拟环境..."
        python3 -m venv .venv
    fi
    
    # 激活虚拟环境并安装依赖
    source .venv/bin/activate
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt >/dev/null 2>&1
    fi
    
    # 启动服务
    nohup uvicorn app:app --host 0.0.0.0 --port 8001 --reload > ../../logs/patient_backend.log 2>&1 &
    local pid=$!
    echo $pid > ../../logs/patient_backend.pid
    
    success "患者端后端已启动 (PID: $pid, 端口: 8001)"
}

# 启动医生端前端 (3000)
start_doctor_frontend() {
    info "启动医生端前端服务 (端口3000)..."
    
    cd "${ROOT_DIR}/frontend"
    
    # 设置环境变量指向医生端后端
    export VITE_API_BASE_URL="http://localhost:8000/api/v1"
    export PORT=3000
    
    # 启动服务
    nohup npm run dev -- --port 3000 > ../logs/doctor_frontend.log 2>&1 &
    local pid=$!
    echo $pid > ../logs/doctor_frontend.pid
    
    success "医生端前端已启动 (PID: $pid, 端口: 3000)"
}

# 启动患者端前端 (3001)
start_patient_frontend() {
    info "启动患者端前端服务 (端口3001)..."
    
    cd "${ROOT_DIR}/frontend"
    
    # 设置环境变量指向患者端后端
    export VITE_API_BASE_URL="http://localhost:8001/api/v1"
    export PORT=3001
    
    # 启动服务
    nohup npm run dev -- --port 3001 > ../logs/patient_frontend.log 2>&1 &
    local pid=$!
    echo $pid > ../logs/patient_frontend.pid
    
    success "患者端前端已启动 (PID: $pid, 端口: 3001)"
}

# 等待服务启动
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=0
    
    info "等待 ${service_name} 启动 (端口: ${port})..."
    
    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s "http://localhost:${port}" >/dev/null 2>&1 || \
           curl -s "http://localhost:${port}/health" >/dev/null 2>&1 || \
           curl -s "http://localhost:${port}/api/v1/health" >/dev/null 2>&1; then
            success "${service_name} 已就绪 (端口: ${port})"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 2
    done
    
    warn "${service_name} 启动超时，但进程可能仍在初始化中"
    return 1
}

# 显示服务状态
show_status() {
    info "服务状态检查..."
    echo ""
    echo "=== 服务列表 ==="
    echo "医生端后端: http://localhost:8000"
    echo "医生端前端: http://localhost:3000"
    echo "患者端后端: http://localhost:8001"
    echo "患者端前端: http://localhost:3001"
    echo ""
    
    # 检查各服务状态
    for port_service in "8000:医生端后端" "3000:医生端前端" "8001:患者端后端" "3001:患者端前端"; do
        local port=$(echo $port_service | cut -d: -f1)
        local service=$(echo $port_service | cut -d: -f2)
        
        if curl -s --connect-timeout 3 "http://localhost:${port}" >/dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} ${service} (端口 ${port}) - 运行中"
        else
            echo -e "${RED}✗${NC} ${service} (端口 ${port}) - 未响应"
        fi
    done
    
    echo ""
    echo "=== 日志文件 ==="
    echo "医生端后端日志: logs/doctor_backend.log"
    echo "医生端前端日志: logs/doctor_frontend.log"
    echo "患者端后端日志: logs/patient_backend.log"
    echo "患者端前端日志: logs/patient_frontend.log"
}

# 主函数
main() {
    info "RAG医疗系统 - 启动所有服务"
    echo "医生端: 后端8000, 前端3000"
    echo "患者端: 后端8001, 前端3001"
    echo ""
    
    # 创建日志目录
    mkdir -p "${ROOT_DIR}/logs"
    
    # 检查依赖
    check_dependencies
    
    # 关闭端口占用
    kill_port 8000 "医生端后端"
    kill_port 3000 "医生端前端"
    kill_port 8001 "患者端后端"
    kill_port 3001 "患者端前端"
    
    # 设置环境
    setup_python_env
    setup_frontend_deps
    
    info "启动所有服务..."
    
    # 启动后端服务
    start_doctor_backend
    start_patient_backend
    
    # 等待后端启动
    sleep 5
    
    # 启动前端服务
    start_doctor_frontend
    start_patient_frontend
    
    # 等待服务启动
    sleep 10
    
    # 显示状态
    show_status
    
    success "所有服务启动完成！"
    info "使用 'tail -f logs/*.log' 查看实时日志"
    info "使用 './stop_all_services.sh' 停止所有服务"
}

# 捕获中断信号
trap 'error "启动过程被中断"; exit 1' INT TERM

# 执行主函数
main "$@"