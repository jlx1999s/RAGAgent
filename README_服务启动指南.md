# 医疗多模态RAG系统 - 整合服务启动指南

## 📋 概述

本系统提供了整合的启动脚本，可以一键启动前端和后端服务，并自动处理端口冲突。

## 🚀 快速启动

### 启动所有服务
```bash
./start_integrated_services.sh
```

### 停止所有服务
```bash
./stop_integrated_services.sh
```

## 📊 服务端口配置

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端服务 | 3000 | React前端应用，支持角色切换 |
| 医生端后端 | 8000 | 医生端API服务 |
| 患者端后端 | 8001 | 患者端API服务 |

## 🔧 脚本功能

### `start_integrated_services.sh`
- ✅ 自动检测并清理端口占用
- ✅ 按顺序启动后端服务（医生端 → 患者端）
- ✅ 启动前端服务
- ✅ 健康检查所有服务
- ✅ 生成详细的启动日志
- ✅ 保存进程PID便于管理

### `stop_integrated_services.sh`
- ✅ 优雅停止所有服务
- ✅ 强制清理残留进程
- ✅ 释放所有占用端口
- ✅ 清理临时文件
- ✅ 最终状态验证

## 📝 日志管理

启动后，日志文件将保存在 `logs/` 目录：

```
logs/
├── frontend.log          # 前端服务日志
├── doctor_backend.log    # 医生端后端日志
├── patient_backend.log   # 患者端后端日志
├── frontend.pid          # 前端进程PID
├── doctor_backend.pid    # 医生端后端进程PID
└── patient_backend.pid   # 患者端后端进程PID
```

## 🔍 故障排除

### 端口被占用
脚本会自动处理端口冲突，如果仍有问题，可以手动检查：
```bash
# 检查端口占用
lsof -i:3000  # 前端
lsof -i:8000  # 医生端后端
lsof -i:8001  # 患者端后端

# 手动终止进程
kill -9 <PID>
```

### 服务启动失败
1. 检查对应的日志文件
2. 确保虚拟环境已正确配置
3. 验证依赖是否已安装

### 前端依赖问题
如果前端启动失败，可能需要重新安装依赖：
```bash
cd frontend
npm install
```

## 🌐 访问地址

启动成功后，可以通过以下地址访问：

- **前端应用**: http://localhost:3000
  - 支持医生/患者角色切换
  - 统一的用户界面
  
- **医生端API**: http://localhost:8000
  - 医生专用功能
  - API文档: http://localhost:8000/docs
  
- **患者端API**: http://localhost:8001
  - 患者专用功能
  - API文档: http://localhost:8001/docs

## 🔄 开发模式

如果需要单独启动某个服务进行开发：

### 前端开发
```bash
cd frontend
npm run dev
```

### 医生端后端开发
```bash
cd backend
source .venv/bin/activate  # 如果使用虚拟环境
python app.py
```

### 患者端后端开发
```bash
cd backend/patient
source .venv/bin/activate  # 如果使用虚拟环境
python app.py
```

## 📋 系统要求

- Node.js (推荐 v16+)
- Python 3.8+
- 所需的Python包（见requirements.txt）
- 足够的系统资源运行3个服务

## 🎯 角色切换功能

前端应用支持在医生和患者角色之间切换：
- 点击右上角的角色切换按钮
- 系统会自动连接到对应的后端服务
- 切换时会清理当前会话状态

## 🛠️ 维护建议

1. 定期检查日志文件大小，必要时清理
2. 监控系统资源使用情况
3. 定期更新依赖包
4. 备份重要的配置文件

---

💡 **提示**: 首次使用前，请确保所有依赖已正确安装，并且系统有足够的权限访问指定端口。