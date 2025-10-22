#!/bin/bash

# 医疗多模态RAG系统 - 整合服务启动脚本
# 启动前端（端口3000）、医生端后端（端口8000）、患者端后端（端口8001）

echo "🚀 启动医疗多模态RAG系统整合服务..."

# 定义端口
FRONTEND_PORT=3000
DOCTOR_BACKEND_PORT=8000
PATIENT_BACKEND_PORT=8001

# 设置环境变量
export REDIS_URL="redis://localhost:6379/0"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="password"
echo "🔧 设置Redis环境变量: $REDIS_URL"

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

# 函数：检查Redis服务状态
check_redis_service() {
    echo "🔍 检查Redis服务状态..."
    
    # 检查Redis是否运行
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis服务运行正常"
        return 0
    else
        echo "⚠️  Redis服务未运行，尝试启动..."
        return 1
    fi
}

# 函数：启动Redis服务
start_redis_service() {
    echo "🚀 启动Redis服务..."
    
    # 检查是否安装了Redis
    if ! command -v redis-server &> /dev/null; then
        echo "❌ 错误：Redis未安装，请先安装Redis"
        echo "   macOS: brew install redis"
        echo "   Ubuntu: sudo apt-get install redis-server"
        echo "   CentOS: sudo yum install redis"
        return 1
    fi
    
    # 尝试启动Redis服务
    if command -v brew &> /dev/null && brew services list | grep redis > /dev/null; then
        # macOS with Homebrew
        echo "📦 使用Homebrew启动Redis..."
        brew services start redis
        sleep 3
    elif command -v systemctl &> /dev/null; then
        # Linux with systemd
        echo "🐧 使用systemctl启动Redis..."
        sudo systemctl start redis-server
        sleep 3
    else
        # 手动启动Redis
        echo "🔧 手动启动Redis服务..."
        nohup redis-server > logs/redis.log 2>&1 &
        sleep 3
    fi
    
    # 验证Redis是否启动成功
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis服务启动成功"
        return 0
    else
        echo "❌ Redis服务启动失败"
        return 1
    fi
}

# 函数：检查Neo4j服务状态
check_neo4j_service() {
    echo "🔍 检查Neo4j服务状态..."
    
    # 检查Neo4j是否运行 (默认端口7687)
    if timeout 5 bash -c "</dev/tcp/localhost/7687" > /dev/null 2>&1; then
        echo "✅ Neo4j服务运行正常"
        return 0
    else
        echo "⚠️  Neo4j服务未运行，尝试启动..."
        return 1
    fi
}

# 函数：启动Neo4j服务
start_neo4j_service() {
    echo "🚀 启动Neo4j服务..."
    
    # 检查是否安装了Neo4j
    if ! command -v neo4j &> /dev/null; then
        echo "❌ 错误：Neo4j未安装，请先安装Neo4j"
        echo "   macOS: brew install neo4j"
        echo "   Ubuntu: 请参考Neo4j官方文档安装"
        echo "   或使用Docker: docker run -d -p 7474:7474 -p 7687:7687 neo4j:latest"
        return 1
    fi
    
    # 尝试启动Neo4j服务
    if command -v brew &> /dev/null && brew services list | grep neo4j > /dev/null; then
        # macOS with Homebrew
        echo "📦 使用Homebrew启动Neo4j..."
        brew services start neo4j
        sleep 5
    elif command -v systemctl &> /dev/null; then
        # Linux with systemd
        echo "🐧 使用systemctl启动Neo4j..."
        sudo systemctl start neo4j
        sleep 5
    else
        # 手动启动Neo4j
        echo "🔧 手动启动Neo4j服务..."
        nohup neo4j start > logs/neo4j.log 2>&1 &
        sleep 5
    fi
    
    # 验证Neo4j是否启动成功
    if timeout 10 bash -c "</dev/tcp/localhost/7687" > /dev/null 2>&1; then
        echo "✅ Neo4j服务启动成功"
        return 0
    else
        echo "❌ Neo4j服务启动失败"
        return 1
    fi
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

# 检查并启动Redis服务
echo "🔴 检查Redis服务..."
if ! check_redis_service; then
    if ! start_redis_service; then
        echo "❌ Redis服务启动失败，将使用内存缓存作为回退方案"
        echo "⚠️  建议手动启动Redis以获得更好的性能"
    fi
fi

# 检查并启动Neo4j服务
echo "🔵 检查Neo4j服务..."
if ! check_neo4j_service; then
    if ! start_neo4j_service; then
        echo "❌ Neo4j服务启动失败，将使用NetworkX作为回退方案"
        echo "⚠️  建议手动启动Neo4j以获得更好的图数据库性能"
    fi
fi

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

# 检查Redis服务
echo "🔴 检查Redis缓存服务..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis缓存服务运行正常: redis://localhost:6379"
    # 显示Redis信息
    redis_info=$(redis-cli info server | grep redis_version | cut -d: -f2 | tr -d '\r')
    echo "   Redis版本: $redis_info"
else
    echo "⚠️  Redis缓存服务未运行，系统将使用内存缓存"
fi

# 检查Neo4j服务
echo "🔵 检查Neo4j图数据库服务..."
if timeout 5 bash -c "</dev/tcp/localhost/7687" > /dev/null 2>&1; then
    echo "✅ Neo4j图数据库服务运行正常: bolt://localhost:7687"
    # 尝试获取Neo4j版本信息
    if command -v cypher-shell &> /dev/null; then
        neo4j_version=$(echo "CALL dbms.components() YIELD name, versions RETURN name, versions[0] as version" | cypher-shell -u neo4j -p password --format plain 2>/dev/null | grep "Neo4j Kernel" | awk '{print $3}' | tr -d '"' || echo "未知")
        echo "   Neo4j版本: $neo4j_version"
    fi
else
    echo "⚠️  Neo4j图数据库服务未运行，系统将使用NetworkX作为回退"
fi

echo ""
echo "🎉 医疗多模态RAG系统整合服务启动完成！"
echo ""
echo "📋 服务信息："
echo "   🌐 前端服务:     http://localhost:$FRONTEND_PORT"
echo "   🏥 医生端后端:   http://localhost:$DOCTOR_BACKEND_PORT"
echo "   🤒 患者端后端:   http://localhost:$PATIENT_BACKEND_PORT"
if redis-cli ping > /dev/null 2>&1; then
    echo "   🔴 Redis缓存:    redis://localhost:6379 (已启用)"
else
    echo "   🔴 Redis缓存:    未运行 (使用内存缓存)"
fi
if timeout 5 bash -c "</dev/tcp/localhost/7687" > /dev/null 2>&1; then
    echo "   🔵 Neo4j图数据库: bolt://localhost:7687 (已启用)"
else
    echo "   🔵 Neo4j图数据库: 未运行 (使用NetworkX)"
fi
echo ""
echo "📝 日志文件："
echo "   前端日志:       logs/frontend.log"
echo "   医生端后端日志: logs/doctor_backend.log"
echo "   患者端后端日志: logs/patient_backend.log"
if [ -f "logs/redis.log" ]; then
    echo "   Redis日志:      logs/redis.log"
fi
if [ -f "logs/neo4j.log" ]; then
    echo "   Neo4j日志:      logs/neo4j.log"
fi
echo ""
echo "🛑 停止服务请运行: ./stop_integrated_services.sh"
echo ""

# 保存PID到文件，方便后续停止服务
echo $FRONTEND_PID > logs/frontend.pid
echo $DOCTOR_PID > logs/doctor_backend.pid
echo $PATIENT_PID > logs/patient_backend.pid

echo "✅ 服务PID已保存到logs目录"