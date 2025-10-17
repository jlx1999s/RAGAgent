# 患者端API接口参考

## 基础信息
- **后端地址**: `http://localhost:8001`
- **API前缀**: `/api/v1`

## 主要接口

### 1. 医疗问答接口

**接口地址**: `POST /api/v1/medical/qa`

**功能**: 基于医疗知识库和可选的体检报告提供医疗问答服务

#### 请求参数

```json
{
  "message": "string",              // 必填：用户的医疗问题
  "sessionId": "string",            // 必填：会话ID
  "medicalReport": "string",        // 可选：体检报告内容
  "reportType": "string",           // 可选：体检报告类型
  "department": "string",           // 可选：科室
  "documentType": "string",         // 可选：文档类型
  "diseaseCategory": "string",      // 可选：疾病分类
  "enableSafetyCheck": boolean,     // 可选：是否启用安全检查，默认true
  "intentRecognitionMethod": "string" // 可选：意图识别方法，默认"qwen_llm"
}
```

#### 体检报告类型 (reportType)
- `血常规`
- `尿常规`
- `肝功能`
- `肾功能`
- `血脂`
- `血糖`
- `甲状腺功能`
- `心电图`
- `胸片`
- `B超`
- `CT`
- `MRI`

#### 响应示例

```json
{
  "answer": "基于您的血常规报告...",
  "citations": [
    {
      "id": "med-c1",
      "content": "引用内容",
      "source": "来源文档",
      "page": 1
    }
  ],
  "retrieval_metadata": {
    "total_chunks": 10,
    "used_chunks": 3,
    "intent": {
      "department": "内科",
      "document_type": "临床指南",
      "confidence": 0.95
    }
  },
  "quality_assessment": {
    "quality_level": "high",
    "quality_score": 0.85,
    "safety_level": "safe"
  },
  "session_id": "test-session-1"
}
```

### 2. 医疗统计接口

**接口地址**: `GET /api/v1/medical/statistics`

**功能**: 获取医疗知识库统计信息

#### 响应示例

```json
{
  "total_documents": 150,
  "total_chunks": 5000,
  "departments": ["内科", "外科", "儿科"],
  "document_types": ["临床指南", "诊疗规范"],
  "last_updated": "2024-01-15T10:30:00Z"
}
```

### 3. 知识库管理接口

**接口地址**: `GET /api/v1/knowledge-base`

**功能**: 获取知识库列表

#### 响应示例

```json
{
  "knowledge_bases": [
    {
      "id": "medical_kb_1",
      "name": "临床医学知识库",
      "description": "包含各科室临床指南",
      "document_count": 50,
      "last_updated": "2024-01-15T10:30:00Z"
    }
  ]
}
```

## curl 测试示例

### 基础医疗问答

```bash
curl -X POST "http://localhost:8001/api/v1/medical/qa" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "感冒了应该怎么办？",
    "sessionId": "test-session-1",
    "enableSafetyCheck": true,
    "intentRecognitionMethod": "qwen_llm"
  }'
```

### 带体检报告的医疗问答

```bash
curl -X POST "http://localhost:8001/api/v1/medical/qa" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我的血常规报告有什么问题吗？",
    "sessionId": "test-session-2",
    "medicalReport": "血常规检查报告：\n白细胞计数：12.5 × 10^9/L (正常值：4.0-10.0)\n红细胞计数：3.8 × 10^12/L (正常值：4.0-5.5)\n血红蛋白：95 g/L (正常值：120-160)",
    "reportType": "血常规",
    "enableSafetyCheck": true,
    "intentRecognitionMethod": "qwen_llm"
  }'
```

### 获取医疗统计

```bash
curl -X GET "http://localhost:8001/api/v1/medical/statistics" \
  -H "Content-Type: application/json"
```

## 注意事项

1. **体检报告格式**: 建议使用结构化格式，包含检查项目、数值和正常值范围
2. **安全检查**: 建议始终启用安全检查以确保回答的安全性
3. **会话管理**: 使用唯一的sessionId来跟踪对话上下文
4. **错误处理**: API会返回相应的HTTP状态码和错误信息

## 错误码说明

- `200`: 成功
- `400`: 请求参数错误
- `422`: 参数验证失败
- `500`: 服务器内部错误