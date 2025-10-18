#!/bin/bash

# 医疗多模态RAG系统 - 整合服务启动脚本
# 启动前端（端口3000）、医生端后端（端口8000）、患者端后端（端口8001）

echo "🚀 启动医疗多模态RAG系统整合服务..."

# 定义端口
FRONTEND_PORT=3000
DOCTOR_BACKEND_PORT=8000
PATIENT_BACKEND_PORT=8001

# 函数：清理指定端口的进程
cleanup_port() {
    local port=$1
    local service_name=$2
    
    echo "🔍 检查端口 $port 的占用情况..."
    
    # 查找占用端口的进程
    local pid=$(lsof -ti:$port)
    
    if [ ! -z "$pid" ]; then
        echo "⚠️  发现端口 $port 被进程 $pid 占用，正在终止..."
        kill -9 $pid 2>/dev/null
        sleep 1
        
        # 再次检查是否成功终止
        local check_pid=$(lsof -ti:$port)
        if [ -z "$check_pid" ]; then
            echo "✅ 端口 $port ($service_name) 已清理完成"
        else
            echo "❌ 端口 $port ($service_name) 清理失败，请手动处理"
            return 1
        fi
    else
        echo "✅ 端口 $port ($service_name) 未被占用"
    fi
}

# 函数：检查目录是否存在
check_directory() {
    local dir=$1
    local service_name=$2
    
    if [ ! -d "$dir" ]; then
        echo "❌ 错误：$service_name 目录不存在: $dir"
        return 1
    fi
    return 0
}

# 清理所有端口
echo "🧹 清理端口占用..."
cleanup_port $FRONTEND_PORT "前端服务"
cleanup_port $DOCTOR_BACKEND_PORT "医生端后端"
cleanup_port $PATIENT_BACKEND_PORT "患者端后端"

echo ""

# 检查必要的目录
echo "📁 检查项目目录..."
check_directory "./frontend" "前端" || exit 1
check_directory "./backend" "医生端后端" || exit 1
check_directory "./backend/patient" "患者端后端" || exit 1

echo ""

# 启动服务
echo "🚀 启动服务..."

# 创建日志目录
mkdir -p logs

# 启动医生端后端服务 (端口8000)
echo "🏥 启动医生端后端服务 (端口 $DOCTOR_BACKEND_PORT)..."
cd backend
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ 已激活医生端虚拟环境"
fi
nohup python app.py > ../logs/doctor_backend.log 2>&1 &
DOCTOR_PID=$!
echo "✅ 医生端后端服务已启动 (PID: $DOCTOR_PID)"
cd ..

# 等待医生端后端启动并检查
echo "⏳ 等待医生端后端启动..."
for i in {1..30}; do
    if curl -s http://localhost:$DOCTOR_BACKEND_PORT/health > /dev/null 2>&1; then
        echo "✅ 医生端后端服务启动成功"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️  医生端后端启动超时，继续启动其他服务..."
    fi
    sleep 2
done

# 启动患者端后端服务 (端口8001)
echo "🤒 启动患者端后端服务 (端口 $PATIENT_BACKEND_PORT)..."
cd backend/patient
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ 已激活患者端虚拟环境"
fi
nohup python app.py > ../../logs/patient_backend.log 2>&1 &
PATIENT_PID=$!
echo "✅ 患者端后端服务已启动 (PID: $PATIENT_PID)"
cd ../..

# 等待患者端后端启动并检查
echo "⏳ 等待患者端后端启动..."
for i in {1..30}; do
    if curl -s http://localhost:$PATIENT_BACKEND_PORT/health > /dev/null 2>&1; then
        echo "✅ 患者端后端服务启动成功"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️  患者端后端启动超时，继续启动前端服务..."
    fi
    sleep 2
done

# 启动前端服务 (端口3000)
echo "🌐 启动前端服务 (端口 $FRONTEND_PORT)..."
cd frontend

# 检查是否有node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 安装前端依赖..."
    npm install
fi

# 设置前端端口为3000并启动
export PORT=$FRONTEND_PORT
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "✅ 前端服务已启动 (PID: $FRONTEND_PID)"
cd ..

# 等待前端服务启动
echo "⏳ 等待前端服务启动..."
for i in {1..20}; do
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        echo "✅ 前端服务启动成功"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "⚠️  前端服务启动超时"
    fi
    sleep 3
done

# 检查服务状态
echo ""
echo "🔍 检查服务状态..."

# 检查前端服务
if curl -s http://localhost:$FRONTEND_PORT > /dev/null; then
    echo "✅ 前端服务运行正常: http://localhost:$FRONTEND_PORT"
else
    echo "❌ 前端服务启动失败"
fi

# 检查医生端后端服务
if curl -s http://localhost:$DOCTOR_BACKEND_PORT/health > /dev/null; then
    echo "✅ 医生端后端服务运行正常: http://localhost:$DOCTOR_BACKEND_PORT"
else
    echo "❌ 医生端后端服务启动失败"
fi

# 检查患者端后端服务
if curl -s http://localhost:$PATIENT_BACKEND_PORT/health > /dev/null; then
    echo "✅ 患者端后端服务运行正常: http://localhost:$PATIENT_BACKEND_PORT"
else
    echo "❌ 患者端后端服务启动失败"
fi

echo ""
echo "🎉 医疗多模态RAG系统整合服务启动完成！"
echo ""
echo "📋 服务信息："
echo "   🌐 前端服务:     http://localhost:$FRONTEND_PORT"
echo "   🏥 医生端后端:   http://localhost:$DOCTOR_BACKEND_PORT"
echo "   🤒 患者端后端:   http://localhost:$PATIENT_BACKEND_PORT"
echo ""
echo "📝 日志文件："
echo "   前端日志:       logs/frontend.log"
echo "   医生端后端日志: logs/doctor_backend.log"
echo "   患者端后端日志: logs/patient_backend.log"
echo ""
echo "🛑 停止服务请运行: ./stop_integrated_services.sh"
echo ""

# 保存PID到文件，方便后续停止服务
echo $FRONTEND_PID > logs/frontend.pid
echo $DOCTOR_PID > logs/doctor_backend.pid
echo $PATIENT_PID > logs/patient_backend.pid

echo "✅ 服务PID已保存到logs目录"