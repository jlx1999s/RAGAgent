#!/usr/bin/env bash
set -euo pipefail

# RAG医疗系统 - 停止所有服务脚本

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

# 停止指定端口的服务
stop_port() {
    local port=$1
    local service_name=$2
    
    info "停止 ${service_name} (端口: ${port})"
    
    if command -v lsof >/dev/null 2>&1; then
        local pids=$(lsof -ti tcp:${port} 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            info "发现进程: $pids"
            echo "$pids" | xargs kill -TERM 2>/dev/null || true
            sleep 3
            
            # 检查是否还有进程
            local remaining_pids=$(lsof -ti tcp:${port} 2>/dev/null || true)
            if [[ -n "$remaining_pids" ]]; then
                warn "强制终止进程: $remaining_pids"
                echo "$remaining_pids" | xargs kill -9 2>/dev/null || true
                sleep 1
            fi
            
            success "${service_name} 已停止"
        else
            info "${service_name} 未运行"
        fi
    else
        warn "lsof 命令不可用，跳过端口检查"
    fi
}

# 通过PID文件停止服务
stop_by_pid() {
    local pid_file=$1
    local service_name=$2
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            info "停止 ${service_name} (PID: $pid)"
            kill -TERM "$pid" 2>/dev/null || true
            sleep 2
            
            # 检查进程是否还存在
            if kill -0 "$pid" 2>/dev/null; then
                warn "强制终止 ${service_name} (PID: $pid)"
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            success "${service_name} 已停止"
        else
            info "${service_name} 进程不存在"
        fi
        
        # 删除PID文件
        rm -f "$pid_file"
    else
        info "${service_name} PID文件不存在"
    fi
}

# 主函数
main() {
    info "RAG医疗系统 - 停止所有服务"
    echo ""
    
    cd "${ROOT_DIR}"
    
    # 通过PID文件停止服务
    stop_by_pid "logs/doctor_backend.pid" "医生端后端"
    stop_by_pid "logs/doctor_frontend.pid" "医生端前端"
    stop_by_pid "logs/patient_backend.pid" "患者端后端"
    stop_by_pid "logs/patient_frontend.pid" "患者端前端"
    
    # 通过端口停止服务（备用方法）
    stop_port 8000 "医生端后端"
    stop_port 3000 "医生端前端"
    stop_port 8001 "患者端后端"
    stop_port 3001 "患者端前端"
    
    # 清理日志文件（可选）
    if [[ "${1:-}" == "--clean-logs" ]]; then
        info "清理日志文件..."
        rm -f logs/*.log
        success "日志文件已清理"
    fi
    
    success "所有服务已停止"
    info "使用 './start_all_services.sh' 重新启动所有服务"
}

# 捕获中断信号
trap 'error "停止过程被中断"; exit 1' INT TERM

# 执行主函数
main "$@"