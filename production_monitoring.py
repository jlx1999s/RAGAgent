#!/usr/bin/env python3
"""
生产环境监控脚本
实时监控RAGAgent系统的健康状态、性能指标和资源使用情况
"""

import asyncio
import aiohttp
import psutil
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ServiceStatus:
    """服务状态数据类"""
    name: str
    url: str
    port: int
    status: str  # 'healthy', 'unhealthy', 'unknown'
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    last_check: Optional[datetime] = None
    uptime: Optional[float] = None

@dataclass
class SystemMetrics:
    """系统指标数据类"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_sent_mb: float
    network_recv_mb: float
    load_average: List[float]

@dataclass
class ServiceMetrics:
    """服务指标数据类"""
    service_name: str
    timestamp: datetime
    process_count: int
    cpu_percent: float
    memory_mb: float
    connections: int
    file_descriptors: int

class ProductionMonitor:
    """生产环境监控器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.services = self._init_services()
        self.session: Optional[aiohttp.ClientSession] = None
        self.monitoring = False
        self.metrics_history: List[SystemMetrics] = []
        self.service_metrics_history: Dict[str, List[ServiceMetrics]] = {}
        
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """加载监控配置"""
        default_config = {
            "check_interval": 30,  # 检查间隔（秒）
            "timeout": 10,  # 请求超时（秒）
            "max_history": 100,  # 最大历史记录数
            "alert_thresholds": {
                "cpu_percent": 80,
                "memory_percent": 85,
                "disk_percent": 90,
                "response_time": 5.0
            },
            "services": {
                "doctor_backend": {"port": 8000, "path": "/health"},
                "patient_backend": {"port": 8001, "path": "/health"},
                "doctor_frontend": {"port": 3000, "path": "/"},
                "patient_frontend": {"port": 3001, "path": "/"}
            }
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.warning(f"无法加载配置文件 {config_file}: {e}")
        
        return default_config
    
    def _init_services(self) -> List[ServiceStatus]:
        """初始化服务列表"""
        services = []
        for name, config in self.config["services"].items():
            port = config["port"]
            path = config.get("path", "/")
            url = f"http://localhost:{port}{path}"
            
            services.append(ServiceStatus(
                name=name,
                url=url,
                port=port,
                status="unknown"
            ))
        
        return services
    
    async def _create_session(self):
        """创建HTTP会话"""
        timeout = aiohttp.ClientTimeout(total=self.config["timeout"])
        self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def _close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
    
    async def check_service_health(self, service: ServiceStatus) -> ServiceStatus:
        """检查单个服务健康状态"""
        start_time = time.time()
        
        try:
            async with self.session.get(service.url) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    service.status = "healthy"
                    service.response_time = response_time
                    service.error_message = None
                else:
                    service.status = "unhealthy"
                    service.error_message = f"HTTP {response.status}"
                    
        except asyncio.TimeoutError:
            service.status = "unhealthy"
            service.error_message = "请求超时"
            service.response_time = None
        except Exception as e:
            service.status = "unhealthy"
            service.error_message = str(e)
            service.response_time = None
        
        service.last_check = datetime.now()
        return service
    
    async def check_all_services(self) -> List[ServiceStatus]:
        """检查所有服务健康状态"""
        if not self.session:
            await self._create_session()
        
        tasks = [self.check_service_health(service) for service in self.services]
        return await asyncio.gather(*tasks)
    
    def get_system_metrics(self) -> SystemMetrics:
        """获取系统指标"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        disk_used_gb = disk.used / (1024**3)
        disk_total_gb = disk.total / (1024**3)
        
        # 网络使用情况
        network = psutil.net_io_counters()
        network_sent_mb = network.bytes_sent / (1024**2)
        network_recv_mb = network.bytes_recv / (1024**2)
        
        # 系统负载
        load_average = list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_percent=disk.percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            load_average=load_average
        )
    
    def get_service_metrics(self, service_name: str, port: int) -> Optional[ServiceMetrics]:
        """获取服务指标"""
        try:
            # 查找服务进程
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if f":{port}" in cmdline or f"port {port}" in cmdline:
                        processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not processes:
                return None
            
            # 聚合进程指标
            total_cpu = 0
            total_memory = 0
            total_connections = 0
            total_fds = 0
            
            for proc in processes:
                try:
                    total_cpu += proc.cpu_percent()
                    total_memory += proc.memory_info().rss / (1024**2)  # MB
                    total_connections += len(proc.connections())
                    total_fds += proc.num_fds() if hasattr(proc, 'num_fds') else 0
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return ServiceMetrics(
                service_name=service_name,
                timestamp=datetime.now(),
                process_count=len(processes),
                cpu_percent=total_cpu,
                memory_mb=total_memory,
                connections=total_connections,
                file_descriptors=total_fds
            )
            
        except Exception as e:
            logger.error(f"获取服务 {service_name} 指标失败: {e}")
            return None
    
    def check_alerts(self, system_metrics: SystemMetrics, services: List[ServiceStatus]):
        """检查告警条件"""
        thresholds = self.config["alert_thresholds"]
        alerts = []
        
        # 系统资源告警
        if system_metrics.cpu_percent > thresholds["cpu_percent"]:
            alerts.append(f"🚨 CPU使用率过高: {system_metrics.cpu_percent:.1f}%")
        
        if system_metrics.memory_percent > thresholds["memory_percent"]:
            alerts.append(f"🚨 内存使用率过高: {system_metrics.memory_percent:.1f}%")
        
        if system_metrics.disk_percent > thresholds["disk_percent"]:
            alerts.append(f"🚨 磁盘使用率过高: {system_metrics.disk_percent:.1f}%")
        
        # 服务健康告警
        for service in services:
            if service.status == "unhealthy":
                alerts.append(f"🚨 服务异常: {service.name} - {service.error_message}")
            elif service.response_time and service.response_time > thresholds["response_time"]:
                alerts.append(f"⚠️ 响应时间过长: {service.name} - {service.response_time:.2f}s")
        
        # 输出告警
        for alert in alerts:
            logger.warning(alert)
            print(f"\033[91m{alert}\033[0m")  # 红色输出
    
    def print_status_report(self, system_metrics: SystemMetrics, services: List[ServiceStatus]):
        """打印状态报告"""
        print("\n" + "="*80)
        print(f"📊 RAGAgent 生产环境监控报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # 系统指标
        print("\n🖥️  系统资源:")
        print(f"  CPU使用率:    {system_metrics.cpu_percent:6.1f}%")
        print(f"  内存使用率:   {system_metrics.memory_percent:6.1f}% ({system_metrics.memory_used_gb:.1f}GB / {system_metrics.memory_total_gb:.1f}GB)")
        print(f"  磁盘使用率:   {system_metrics.disk_percent:6.1f}% ({system_metrics.disk_used_gb:.1f}GB / {system_metrics.disk_total_gb:.1f}GB)")
        print(f"  网络流量:     ↑{system_metrics.network_sent_mb:.1f}MB ↓{system_metrics.network_recv_mb:.1f}MB")
        print(f"  系统负载:     {system_metrics.load_average[0]:.2f} {system_metrics.load_average[1]:.2f} {system_metrics.load_average[2]:.2f}")
        
        # 服务状态
        print("\n🚀 服务状态:")
        for service in services:
            status_icon = "✅" if service.status == "healthy" else "❌" if service.status == "unhealthy" else "❓"
            response_info = f"({service.response_time:.3f}s)" if service.response_time else ""
            error_info = f"- {service.error_message}" if service.error_message else ""
            
            print(f"  {status_icon} {service.name:20} (:{service.port}) {response_info} {error_info}")
        
        # 服务指标
        print("\n📈 服务指标:")
        for service in services:
            metrics = self.get_service_metrics(service.name, service.port)
            if metrics:
                print(f"  📊 {service.name:20} - 进程:{metrics.process_count} CPU:{metrics.cpu_percent:.1f}% 内存:{metrics.memory_mb:.1f}MB 连接:{metrics.connections}")
        
        print("\n" + "="*80)
    
    def save_metrics_to_file(self, system_metrics: SystemMetrics, services: List[ServiceStatus]):
        """保存指标到文件"""
        try:
            # 确保日志目录存在
            Path("logs").mkdir(exist_ok=True)
            
            # 保存系统指标
            metrics_file = Path("logs/system_metrics.jsonl")
            with open(metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(system_metrics), default=str) + "\n")
            
            # 保存服务状态
            services_file = Path("logs/service_status.jsonl")
            with open(services_file, "a", encoding="utf-8") as f:
                for service in services:
                    f.write(json.dumps(asdict(service), default=str) + "\n")
                    
        except Exception as e:
            logger.error(f"保存指标到文件失败: {e}")
    
    async def monitor_loop(self):
        """监控主循环"""
        logger.info("开始生产环境监控...")
        self.monitoring = True
        
        try:
            while self.monitoring:
                # 获取系统指标
                system_metrics = self.get_system_metrics()
                self.metrics_history.append(system_metrics)
                
                # 限制历史记录数量
                if len(self.metrics_history) > self.config["max_history"]:
                    self.metrics_history.pop(0)
                
                # 检查服务健康状态
                services = await self.check_all_services()
                
                # 检查告警
                self.check_alerts(system_metrics, services)
                
                # 打印状态报告
                self.print_status_report(system_metrics, services)
                
                # 保存指标到文件
                self.save_metrics_to_file(system_metrics, services)
                
                # 等待下次检查
                await asyncio.sleep(self.config["check_interval"])
                
        except KeyboardInterrupt:
            logger.info("监控被用户中断")
        except Exception as e:
            logger.error(f"监控循环出错: {e}")
        finally:
            self.monitoring = False
            await self._close_session()
    
    async def run_once(self):
        """运行一次检查"""
        try:
            # 获取系统指标
            system_metrics = self.get_system_metrics()
            
            # 检查服务健康状态
            services = await self.check_all_services()
            
            # 检查告警
            self.check_alerts(system_metrics, services)
            
            # 打印状态报告
            self.print_status_report(system_metrics, services)
            
            # 保存指标到文件
            self.save_metrics_to_file(system_metrics, services)
            
        finally:
            await self._close_session()

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="RAGAgent生产环境监控")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--once", action="store_true", help="只运行一次检查")
    parser.add_argument("--interval", "-i", type=int, default=30, help="检查间隔（秒）")
    
    args = parser.parse_args()
    
    # 创建监控器
    monitor = ProductionMonitor(args.config)
    
    # 设置检查间隔
    if args.interval != 30:
        monitor.config["check_interval"] = args.interval
    
    try:
        if args.once:
            await monitor.run_once()
        else:
            await monitor.monitor_loop()
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        logger.error(f"监控出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())