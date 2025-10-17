#!/bin/bash
# 患者端API curl测试示例

echo "=== 患者端医疗问答API测试 ==="
echo "后端地址: http://localhost:8001"
echo ""

# 1. 基础医疗问答（无体检报告）
echo "1. 基础医疗问答测试："
curl -X POST "http://localhost:8001/api/v1/medical/qa" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "感冒了应该怎么办？",
    "sessionId": "test-session-1",
    "enableSafetyCheck": true,
    "intentRecognitionMethod": "qwen_llm"
  }' | jq '.'

echo -e "\n" && read -p "按回车继续下一个测试..."

# 2. 带体检报告的医疗问答 - 血常规
echo "2. 血常规体检报告测试："
curl -X POST "http://localhost:8001/api/v1/medical/qa" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我的血常规报告有什么问题吗？需要注意什么？",
    "sessionId": "test-session-2",
    "medicalReport": "血常规检查报告：\n白细胞计数：12.5 × 10^9/L (正常值：4.0-10.0)\n红细胞计数：3.8 × 10^12/L (正常值：4.0-5.5)\n血红蛋白：95 g/L (正常值：120-160)\n血小板计数：180 × 10^9/L (正常值：100-300)\n中性粒细胞百分比：78% (正常值：50-70%)",
    "reportType": "血常规",
    "enableSafetyCheck": true,
    "intentRecognitionMethod": "qwen_llm"
  }' | jq '.'

echo -e "\n" && read -p "按回车继续下一个测试..."

# 3. 带体检报告的医疗问答 - 肝功能
echo "3. 肝功能体检报告测试："
curl -X POST "http://localhost:8001/api/v1/medical/qa" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "根据我的肝功能检查结果，我应该怎么办？",
    "sessionId": "test-session-3",
    "medicalReport": "肝功能检查报告：\n谷丙转氨酶(ALT)：85 U/L (正常值：5-40)\n谷草转氨酶(AST)：92 U/L (正常值：8-40)\n总胆红素：28 μmol/L (正常值：3.4-20.5)\n直接胆红素：18 μmol/L (正常值：0-6.8)\n白蛋白：35 g/L (正常值：35-55)",
    "reportType": "肝功能",
    "enableSafetyCheck": true,
    "intentRecognitionMethod": "qwen_llm"
  }' | jq '.'

echo -e "\n" && read -p "按回车继续下一个测试..."

# 4. 医疗统计信息
echo "4. 医疗统计信息："
curl -X GET "http://localhost:8001/api/v1/medical/statistics" \
  -H "Content-Type: application/json" | jq '.'

echo -e "\n" && read -p "按回车继续下一个测试..."

# 5. 知识库管理 - 获取知识库列表
echo "5. 知识库列表："
curl -X GET "http://localhost:8001/api/v1/knowledge-base" \
  -H "Content-Type: application/json" | jq '.'

echo -e "\n"
echo "=== 测试完成 ==="