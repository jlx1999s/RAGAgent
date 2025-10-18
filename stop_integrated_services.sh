#!/bin/bash

# 医疗多模态RAG系统 - 整合服务停止脚本
# 停止前端、医生端后端、患者端后端服务

echo "🛑 停止医疗多模态RAG系统整合服务..."

# 定义端口
FRONTEND_PORT=3000
DOCTOR_BACKEND_PORT=8000
PATIENT_BACKEND_PORT=8001

# 函数：通过PID停止服务
stop_service_by_pid() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if [ ! -z "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "🔄 停止 $service_name (PID: $pid)..."
            kill -TERM "$pid" 2>/dev/null
            sleep 2
            
            # 检查是否成功停止
            if kill -0 "$pid" 2>/dev/null; then
                echo "⚠️  强制停止 $service_name (PID: $pid)..."
                kill -9 "$pid" 2>/dev/null
            fi
            
            if ! kill -0 "$pid" 2>/dev/null; then
                echo "✅ $service_name 已停止"
            else
                echo "❌ $service_name 停止失败"
            fi
        else
            echo "⚠️  $service_name PID文件存在但进程不存在"
        fi
        rm -f "$pid_file"
    else
        echo "⚠️  未找到 $service_name 的PID文件"
    fi
}

# 函数：通过端口停止服务
stop_service_by_port() {
    local port=$1
    local service_name=$2
    
    echo "🔍 检查端口 $port 的占用情况..."
    
    local pid=$(lsof -ti:$port)
    
    if [ ! -z "$pid" ]; then
        echo "🔄 停止占用端口 $port 的进程 $pid ($service_name)..."
        kill -TERM $pid 2>/dev/null
        sleep 2
        
        # 检查是否成功停止
        local check_pid=$(lsof -ti:$port)
        if [ ! -z "$check_pid" ]; then
            echo "⚠️  强制停止进程 $pid..."
            kill -9 $pid 2>/dev/null
        fi
        
        # 最终检查
        local final_check=$(lsof -ti:$port)
        if [ -z "$final_check" ]; then
            echo "✅ 端口 $port ($service_name) 已释放"
        else
            echo "❌ 端口 $port ($service_name) 释放失败"
        fi
    else
        echo "✅ 端口 $port ($service_name) 未被占用"
    fi
}

# 创建日志目录（如果不存在）
mkdir -p logs

echo "🔄 通过PID文件停止服务..."

# 通过PID文件停止服务
stop_service_by_pid "logs/frontend.pid" "前端服务"
stop_service_by_pid "logs/doctor_backend.pid" "医生端后端服务"
stop_service_by_pid "logs/patient_backend.pid" "患者端后端服务"

echo ""
echo "🔄 通过端口检查并清理残留进程..."

# 通过端口停止可能的残留进程
stop_service_by_port $FRONTEND_PORT "前端服务"
stop_service_by_port $DOCTOR_BACKEND_PORT "医生端后端服务"
stop_service_by_port $PATIENT_BACKEND_PORT "患者端后端服务"

echo ""
echo "🧹 清理临时文件..."

# 清理PID文件
rm -f logs/frontend.pid
rm -f logs/doctor_backend.pid
rm -f logs/patient_backend.pid

echo "✅ PID文件已清理"

echo ""
echo "📋 最终状态检查..."

# 最终检查所有端口是否已释放
all_clear=true

for port in $FRONTEND_PORT $DOCTOR_BACKEND_PORT $PATIENT_BACKEND_PORT; do
    if lsof -ti:$port > /dev/null 2>&1; then
        echo "❌ 端口 $port 仍被占用"
        all_clear=false
    else
        echo "✅ 端口 $port 已释放"
    fi
done

echo ""
if [ "$all_clear" = true ]; then
    echo "🎉 所有服务已成功停止，端口已释放！"
else
    echo "⚠️  部分服务可能未完全停止，请检查上述端口占用情况"
    echo "💡 提示：可以使用以下命令手动检查："
    echo "   lsof -i:$FRONTEND_PORT"
    echo "   lsof -i:$DOCTOR_BACKEND_PORT"
    echo "   lsof -i:$PATIENT_BACKEND_PORT"
fi

echo ""
echo "🚀 如需重新启动服务，请运行: ./start_integrated_services.sh"