#!/bin/bash

# 生产环境停止脚本
# 安全停止所有生产服务

set -euo pipefail

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
LOG_DIR="${ROOT_DIR}/logs"
PID_DIR="${ROOT_DIR}/pids"

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

# 停止服务函数
stop_service() {
    local service_name=$1
    local pid_file="${PID_DIR}/${service_name}.pid"
    local port=$2
    
    info "停止 ${service_name}..."
    
    # 尝试从PID文件停止
    if [[ -f "${pid_file}" ]]; then
        local pid=$(cat "${pid_file}")
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            info "发送TERM信号到进程 ${pid}..."
            kill -TERM "${pid}" 2>/dev/null || true
            
            # 等待进程优雅退出
            local count=0
            while kill -0 "${pid}" 2>/dev/null && [[ $count -lt 30 ]]; do
                sleep 1
                ((count++))
            done
            
            # 如果进程仍在运行，强制杀死
            if kill -0 "${pid}" 2>/dev/null; then
                warn "进程 ${pid} 未响应TERM信号，发送KILL信号..."
                kill -KILL "${pid}" 2>/dev/null || true
                sleep 1
            fi
            
            success "${service_name} 已停止 (PID: ${pid})"
        else
            warn "PID文件中的进程 ${pid} 不存在"
        fi
        
        # 删除PID文件
        rm -f "${pid_file}"
    else
        warn "未找到 ${service_name} 的PID文件"
    fi
    
    # 备用方案：通过端口杀死进程
    if [[ -n "${port}" ]]; then
        local port_pid=$(lsof -ti :${port} 2>/dev/null || true)
        if [[ -n "${port_pid}" ]]; then
            warn "发现端口 ${port} 上仍有进程 ${port_pid}，强制停止..."
            kill -TERM "${port_pid}" 2>/dev/null || true
            sleep 2
            
            if kill -0 "${port_pid}" 2>/dev/null; then
                kill -KILL "${port_pid}" 2>/dev/null || true
            fi
            
            success "端口 ${port} 上的进程已停止"
        fi
    fi
}

# 停止Gunicorn服务
stop_gunicorn_service() {
    local service_name=$1
    local pid_file="${PID_DIR}/${service_name}.pid"
    local port=$2
    
    info "停止 ${service_name} (Gunicorn)..."
    
    # Gunicorn支持优雅重启和停止
    if [[ -f "${pid_file}" ]]; then
        local master_pid=$(cat "${pid_file}")
        if [[ -n "${master_pid}" ]] && kill -0 "${master_pid}" 2>/dev/null; then
            info "发送TERM信号到Gunicorn master进程 ${master_pid}..."
            kill -TERM "${master_pid}" 2>/dev/null || true
            
            # 等待Gunicorn优雅退出
            local count=0
            while kill -0 "${master_pid}" 2>/dev/null && [[ $count -lt 30 ]]; do
                sleep 1
                ((count++))
            done
            
            # 如果master进程仍在运行，强制杀死
            if kill -0 "${master_pid}" 2>/dev/null; then
                warn "Gunicorn master进程 ${master_pid} 未响应，强制停止..."
                kill -KILL "${master_pid}" 2>/dev/null || true
                
                # 同时杀死所有worker进程
                pkill -f "gunicorn.*app:app" 2>/dev/null || true
                sleep 1
            fi
            
            success "${service_name} 已停止 (Master PID: ${master_pid})"
        else
            warn "PID文件中的master进程 ${master_pid} 不存在"
        fi
        
        # 删除PID文件
        rm -f "${pid_file}"
    else
        warn "未找到 ${service_name} 的PID文件"
        
        # 尝试通过进程名停止
        local gunicorn_pids=$(pgrep -f "gunicorn.*app:app.*${port}" 2>/dev/null || true)
        if [[ -n "${gunicorn_pids}" ]]; then
            warn "通过进程名找到Gunicorn进程，停止中..."
            echo "${gunicorn_pids}" | xargs -r kill -TERM 2>/dev/null || true
            sleep 3
            echo "${gunicorn_pids}" | xargs -r kill -KILL 2>/dev/null || true
        fi
    fi
    
    # 确保端口被释放
    if [[ -n "${port}" ]]; then
        local port_pid=$(lsof -ti :${port} 2>/dev/null || true)
        if [[ -n "${port_pid}" ]]; then
            warn "端口 ${port} 仍被占用，强制释放..."
            kill -KILL "${port_pid}" 2>/dev/null || true
        fi
    fi
}

# 清理日志文件
cleanup_logs() {
    if [[ "$1" == "--clean-logs" ]]; then
        info "清理日志文件..."
        rm -f "${LOG_DIR}"/*.log
        success "日志文件已清理"
    fi
}

# 检查服务状态
check_stop_status() {
    info "检查停止状态..."
    
    local services=(
        "8000:医生端后端"
        "8001:患者端后端"
        "3000:医生端前端"
        "3001:患者端前端"
    )
    
    local all_stopped=true
    
    for service in "${services[@]}"; do
        local port="${service%%:*}"
        local name="${service##*:}"
        
        if lsof -i :${port} >/dev/null 2>&1; then
            warn "${name} (端口${port}): ❌ 仍在运行"
            all_stopped=false
        else
            success "${name} (端口${port}): ✅ 已停止"
        fi
    done
    
    if [[ "${all_stopped}" == "true" ]]; then
        success "所有服务已成功停止"
    else
        warn "部分服务可能仍在运行，请手动检查"
    fi
}

# 主函数
main() {
    info "停止生产环境服务..."
    
    # 停止后端服务 (Gunicorn)
    stop_gunicorn_service "doctor_backend" "8000"
    stop_gunicorn_service "patient_backend" "8001"
    
    # 停止前端服务
    stop_service "doctor_frontend" "3000"
    stop_service "patient_frontend" "3001"
    
    # 等待所有进程完全停止
    sleep 3
    
    # 检查停止状态
    check_stop_status
    
    # 清理日志文件（如果指定）
    cleanup_logs "${1:-}"
    
    success "生产环境服务停止完成！"
    
    # 显示清理信息
    echo ""
    echo "📁 文件位置:"
    echo "  - 日志目录: ${LOG_DIR}/"
    echo "  - PID目录: ${PID_DIR}/"
    echo ""
    echo "💡 提示:"
    echo "  - 重新启动: ./start_production.sh"
    echo "  - 清理日志: ./stop_production.sh --clean-logs"
}

# 信号处理
trap 'error "脚本被中断"; exit 1' INT TERM

# 执行主函数
main "$@"