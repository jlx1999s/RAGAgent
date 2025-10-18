#!/usr/bin/env python3
"""
生产环境负载测试脚本
测试RAGAgent系统在高并发情况下的性能表现
"""

import asyncio
import aiohttp
import time
import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import sys
import random

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/load_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class RequestResult:
    """请求结果数据类"""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    response_time: float
    success: bool
    error_message: Optional[str] = None
    response_size: int = 0

@dataclass
class LoadTestConfig:
    """负载测试配置"""
    base_url: str = "http://localhost"
    concurrent_users: int = 10
    requests_per_user: int = 100
    ramp_up_time: int = 30  # 秒
    test_duration: int = 300  # 秒
    request_timeout: int = 30
    think_time_min: float = 0.1  # 最小思考时间
    think_time_max: float = 2.0  # 最大思考时间

@dataclass
class TestScenario:
    """测试场景"""
    name: str
    weight: float  # 权重（0-1）
    endpoint: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    data: Optional[Dict[str, Any]] = None

class LoadTester:
    """负载测试器"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[RequestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_start_time: Optional[datetime] = None
        self.test_end_time: Optional[datetime] = None
        
        # 测试场景
        self.scenarios = self._init_scenarios()
        
    def _init_scenarios(self) -> List[TestScenario]:
        """初始化测试场景"""
        return [
            # 健康检查
            TestScenario(
                name="health_check_doctor",
                weight=0.1,
                endpoint=f"{self.config.base_url}:8000/health",
                method="GET"
            ),
            TestScenario(
                name="health_check_patient",
                weight=0.1,
                endpoint=f"{self.config.base_url}:8001/health",
                method="GET"
            ),
            
            # 医生端API测试
            TestScenario(
                name="doctor_chat",
                weight=0.3,
                endpoint=f"{self.config.base_url}:8000/api/chat",
                method="POST",
                headers={"Content-Type": "application/json"},
                data={
                    "message": "患者出现胸痛症状，请帮助诊断",
                    "session_id": "test_session_doctor"
                }
            ),
            TestScenario(
                name="doctor_medical_search",
                weight=0.2,
                endpoint=f"{self.config.base_url}:8000/api/medical/search",
                method="POST",
                headers={"Content-Type": "application/json"},
                data={
                    "query": "心肌梗死的诊断标准",
                    "limit": 10
                }
            ),
            
            # 患者端API测试
            TestScenario(
                name="patient_chat",
                weight=0.2,
                endpoint=f"{self.config.base_url}:8001/api/chat",
                method="POST",
                headers={"Content-Type": "application/json"},
                data={
                    "message": "我最近感觉胸口疼痛，这是什么原因？",
                    "session_id": "test_session_patient"
                }
            ),
            TestScenario(
                name="patient_upload_pdf",
                weight=0.1,
                endpoint=f"{self.config.base_url}:8001/api/upload-pdf",
                method="POST",
                # 注意：实际测试时需要准备测试PDF文件
            ),
        ]
    
    async def _create_session(self):
        """创建HTTP会话"""
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        connector = aiohttp.TCPConnector(
            limit=self.config.concurrent_users * 2,  # 连接池大小
            limit_per_host=self.config.concurrent_users,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )
    
    async def _close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
    
    def _select_scenario(self) -> TestScenario:
        """根据权重选择测试场景"""
        total_weight = sum(scenario.weight for scenario in self.scenarios)
        random_value = random.random() * total_weight
        
        current_weight = 0
        for scenario in self.scenarios:
            current_weight += scenario.weight
            if random_value <= current_weight:
                return scenario
        
        return self.scenarios[0]  # 默认返回第一个场景
    
    async def _make_request(self, scenario: TestScenario) -> RequestResult:
        """执行单个请求"""
        start_time = time.time()
        timestamp = datetime.now()
        
        try:
            # 准备请求参数
            kwargs = {}
            if scenario.headers:
                kwargs['headers'] = scenario.headers
            if scenario.data:
                kwargs['json'] = scenario.data
            
            # 发送请求
            async with self.session.request(
                scenario.method,
                scenario.endpoint,
                **kwargs
            ) as response:
                response_time = time.time() - start_time
                response_text = await response.text()
                response_size = len(response_text.encode('utf-8'))
                
                return RequestResult(
                    timestamp=timestamp,
                    endpoint=scenario.endpoint,
                    method=scenario.method,
                    status_code=response.status,
                    response_time=response_time,
                    success=200 <= response.status < 400,
                    response_size=response_size
                )
                
        except asyncio.TimeoutError:
            return RequestResult(
                timestamp=timestamp,
                endpoint=scenario.endpoint,
                method=scenario.method,
                status_code=0,
                response_time=time.time() - start_time,
                success=False,
                error_message="请求超时"
            )
        except Exception as e:
            return RequestResult(
                timestamp=timestamp,
                endpoint=scenario.endpoint,
                method=scenario.method,
                status_code=0,
                response_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    async def _user_simulation(self, user_id: int):
        """模拟单个用户的行为"""
        logger.info(f"用户 {user_id} 开始测试")
        
        # 渐进式启动（ramp-up）
        if self.config.ramp_up_time > 0:
            delay = (user_id / self.config.concurrent_users) * self.config.ramp_up_time
            await asyncio.sleep(delay)
        
        requests_made = 0
        start_time = time.time()
        
        while (
            requests_made < self.config.requests_per_user and
            time.time() - start_time < self.config.test_duration
        ):
            # 选择测试场景
            scenario = self._select_scenario()
            
            # 执行请求
            result = await self._make_request(scenario)
            self.results.append(result)
            requests_made += 1
            
            # 思考时间（模拟用户行为）
            think_time = random.uniform(
                self.config.think_time_min,
                self.config.think_time_max
            )
            await asyncio.sleep(think_time)
        
        logger.info(f"用户 {user_id} 完成测试，共发送 {requests_made} 个请求")
    
    async def run_load_test(self):
        """运行负载测试"""
        logger.info(f"开始负载测试 - 并发用户: {self.config.concurrent_users}, 每用户请求数: {self.config.requests_per_user}")
        
        self.test_start_time = datetime.now()
        
        try:
            # 创建HTTP会话
            await self._create_session()
            
            # 创建用户任务
            tasks = [
                self._user_simulation(user_id)
                for user_id in range(self.config.concurrent_users)
            ]
            
            # 并发执行所有用户任务
            await asyncio.gather(*tasks)
            
        finally:
            self.test_end_time = datetime.now()
            await self._close_session()
        
        logger.info("负载测试完成")
    
    def analyze_results(self) -> Dict[str, Any]:
        """分析测试结果"""
        if not self.results:
            return {"error": "没有测试结果"}
        
        # 基本统计
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.success)
        failed_requests = total_requests - successful_requests
        success_rate = (successful_requests / total_requests) * 100
        
        # 响应时间统计
        response_times = [r.response_time for r in self.results if r.success]
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = median_response_time = p95_response_time = p99_response_time = 0
            min_response_time = max_response_time = 0
        
        # 吞吐量计算
        test_duration = (self.test_end_time - self.test_start_time).total_seconds()
        requests_per_second = total_requests / test_duration if test_duration > 0 else 0
        
        # 错误统计
        error_counts = {}
        for result in self.results:
            if not result.success:
                error_key = result.error_message or f"HTTP {result.status_code}"
                error_counts[error_key] = error_counts.get(error_key, 0) + 1
        
        # 端点统计
        endpoint_stats = {}
        for result in self.results:
            endpoint = result.endpoint
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = {
                    "total": 0,
                    "success": 0,
                    "avg_response_time": 0,
                    "response_times": []
                }
            
            endpoint_stats[endpoint]["total"] += 1
            if result.success:
                endpoint_stats[endpoint]["success"] += 1
                endpoint_stats[endpoint]["response_times"].append(result.response_time)
        
        # 计算每个端点的平均响应时间
        for endpoint, stats in endpoint_stats.items():
            if stats["response_times"]:
                stats["avg_response_time"] = statistics.mean(stats["response_times"])
                stats["success_rate"] = (stats["success"] / stats["total"]) * 100
            else:
                stats["avg_response_time"] = 0
                stats["success_rate"] = 0
            del stats["response_times"]  # 删除原始数据以节省空间
        
        return {
            "test_summary": {
                "start_time": self.test_start_time.isoformat(),
                "end_time": self.test_end_time.isoformat(),
                "duration_seconds": test_duration,
                "concurrent_users": self.config.concurrent_users,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate_percent": success_rate,
                "requests_per_second": requests_per_second
            },
            "response_time_stats": {
                "average_ms": avg_response_time * 1000,
                "median_ms": median_response_time * 1000,
                "p95_ms": p95_response_time * 1000,
                "p99_ms": p99_response_time * 1000,
                "min_ms": min_response_time * 1000,
                "max_ms": max_response_time * 1000
            },
            "error_analysis": error_counts,
            "endpoint_performance": endpoint_stats
        }
    
    def print_results(self, analysis: Dict[str, Any]):
        """打印测试结果"""
        print("\n" + "="*80)
        print("📊 RAGAgent 负载测试报告")
        print("="*80)
        
        # 测试摘要
        summary = analysis["test_summary"]
        print(f"\n🎯 测试摘要:")
        print(f"  测试时间:     {summary['start_time']} - {summary['end_time']}")
        print(f"  测试时长:     {summary['duration_seconds']:.1f} 秒")
        print(f"  并发用户:     {summary['concurrent_users']}")
        print(f"  总请求数:     {summary['total_requests']}")
        print(f"  成功请求:     {summary['successful_requests']}")
        print(f"  失败请求:     {summary['failed_requests']}")
        print(f"  成功率:       {summary['success_rate_percent']:.2f}%")
        print(f"  吞吐量:       {summary['requests_per_second']:.2f} 请求/秒")
        
        # 响应时间统计
        response_stats = analysis["response_time_stats"]
        print(f"\n⏱️  响应时间统计:")
        print(f"  平均响应时间: {response_stats['average_ms']:.2f} ms")
        print(f"  中位数:       {response_stats['median_ms']:.2f} ms")
        print(f"  95%分位数:    {response_stats['p95_ms']:.2f} ms")
        print(f"  99%分位数:    {response_stats['p99_ms']:.2f} ms")
        print(f"  最小值:       {response_stats['min_ms']:.2f} ms")
        print(f"  最大值:       {response_stats['max_ms']:.2f} ms")
        
        # 错误分析
        if analysis["error_analysis"]:
            print(f"\n❌ 错误分析:")
            for error, count in analysis["error_analysis"].items():
                print(f"  {error}: {count} 次")
        
        # 端点性能
        print(f"\n🔗 端点性能:")
        for endpoint, stats in analysis["endpoint_performance"].items():
            print(f"  {endpoint}")
            print(f"    请求数: {stats['total']}, 成功率: {stats['success_rate']:.1f}%, 平均响应时间: {stats['avg_response_time']*1000:.2f}ms")
        
        print("\n" + "="*80)
    
    def save_results(self, analysis: Dict[str, Any]):
        """保存测试结果"""
        try:
            # 确保日志目录存在
            Path("logs").mkdir(exist_ok=True)
            
            # 保存详细结果
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = Path(f"logs/load_test_results_{timestamp}.json")
            
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump({
                    "config": asdict(self.config),
                    "analysis": analysis,
                    "raw_results": [asdict(r) for r in self.results]
                }, f, indent=2, default=str)
            
            logger.info(f"测试结果已保存到: {results_file}")
            
        except Exception as e:
            logger.error(f"保存测试结果失败: {e}")

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="RAGAgent负载测试")
    parser.add_argument("--users", "-u", type=int, default=10, help="并发用户数")
    parser.add_argument("--requests", "-r", type=int, default=100, help="每用户请求数")
    parser.add_argument("--duration", "-d", type=int, default=300, help="测试时长（秒）")
    parser.add_argument("--ramp-up", type=int, default=30, help="渐进启动时间（秒）")
    parser.add_argument("--base-url", default="http://localhost", help="基础URL")
    parser.add_argument("--timeout", type=int, default=30, help="请求超时（秒）")
    
    args = parser.parse_args()
    
    # 创建测试配置
    config = LoadTestConfig(
        base_url=args.base_url,
        concurrent_users=args.users,
        requests_per_user=args.requests,
        test_duration=args.duration,
        ramp_up_time=args.ramp_up,
        request_timeout=args.timeout
    )
    
    # 创建负载测试器
    tester = LoadTester(config)
    
    try:
        # 运行负载测试
        await tester.run_load_test()
        
        # 分析结果
        analysis = tester.analyze_results()
        
        # 打印结果
        tester.print_results(analysis)
        
        # 保存结果
        tester.save_results(analysis)
        
    except KeyboardInterrupt:
        print("\n负载测试被用户中断")
    except Exception as e:
        logger.error(f"负载测试出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())