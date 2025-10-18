"""
生产环境部署配置
提供生产级别的服务器配置、连接池设置和性能优化参数
"""

import os
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class ProductionConfig:
    """生产环境配置类"""
    
    # 服务器配置
    workers: int = 4
    worker_class: str = "uvicorn.workers.UvicornWorker"
    worker_connections: int = 1000
    max_requests: int = 1000
    max_requests_jitter: int = 100
    timeout: int = 30
    keepalive: int = 5
    
    # Redis配置
    redis_max_connections: int = 20
    redis_socket_connect_timeout: int = 5
    redis_socket_timeout: int = 5
    redis_retry_on_timeout: bool = True
    redis_health_check_interval: int = 30
    
    # 缓存配置
    cache_max_size: int = 5000
    cache_default_ttl: int = 3600
    vector_store_cache_size: int = 50
    
    # 限流配置
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    
    # 监控配置
    enable_metrics: bool = True
    metrics_port: int = 9090
    log_level: str = "INFO"
    
    # 安全配置
    enable_cors: bool = True
    allowed_origins: list = None
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    
    def __post_init__(self):
        if self.allowed_origins is None:
            self.allowed_origins = ["http://localhost:3000", "http://localhost:3001"]

# 生产环境配置实例
PRODUCTION_CONFIG = ProductionConfig()

# 环境变量覆盖
def load_from_env() -> ProductionConfig:
    """从环境变量加载配置"""
    config = ProductionConfig()
    
    # 服务器配置
    config.workers = int(os.getenv("WORKERS", config.workers))
    config.worker_connections = int(os.getenv("WORKER_CONNECTIONS", config.worker_connections))
    config.max_requests = int(os.getenv("MAX_REQUESTS", config.max_requests))
    config.timeout = int(os.getenv("TIMEOUT", config.timeout))
    
    # Redis配置
    config.redis_max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", config.redis_max_connections))
    config.redis_socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", config.redis_socket_timeout))
    
    # 缓存配置
    config.cache_max_size = int(os.getenv("CACHE_MAX_SIZE", config.cache_max_size))
    config.vector_store_cache_size = int(os.getenv("VECTOR_STORE_CACHE_SIZE", config.vector_store_cache_size))
    
    # 限流配置
    config.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", config.rate_limit_per_minute))
    config.rate_limit_per_hour = int(os.getenv("RATE_LIMIT_PER_HOUR", config.rate_limit_per_hour))
    
    # 日志级别
    config.log_level = os.getenv("LOG_LEVEL", config.log_level)
    
    return config

# Gunicorn配置生成
def generate_gunicorn_config(config: ProductionConfig, port: int = 8000) -> Dict[str, Any]:
    """生成Gunicorn配置"""
    return {
        "bind": f"0.0.0.0:{port}",
        "workers": config.workers,
        "worker_class": config.worker_class,
        "worker_connections": config.worker_connections,
        "max_requests": config.max_requests,
        "max_requests_jitter": config.max_requests_jitter,
        "timeout": config.timeout,
        "keepalive": config.keepalive,
        "preload_app": True,
        "access_log": "-",
        "error_log": "-",
        "log_level": config.log_level.lower(),
        "capture_output": True,
        "enable_stdio_inheritance": True,
    }

# Redis连接配置
def get_redis_config(config: ProductionConfig) -> Dict[str, Any]:
    """获取Redis连接配置"""
    return {
        "max_connections": config.redis_max_connections,
        "socket_connect_timeout": config.redis_socket_connect_timeout,
        "socket_timeout": config.redis_socket_timeout,
        "retry_on_timeout": config.redis_retry_on_timeout,
        "health_check_interval": config.redis_health_check_interval,
        "decode_responses": True,
    }

# 缓存服务配置
def get_cache_config(config: ProductionConfig) -> Dict[str, Any]:
    """获取缓存服务配置"""
    return {
        "max_size": config.cache_max_size,
        "default_ttl": config.cache_default_ttl,
        "ttl_config": {
            'query_result': 1800,      # 查询结果缓存30分钟
            'entity_extraction': 3600,  # 实体提取缓存1小时
            'intent_recognition': 1800, # 意图识别缓存30分钟
            'kg_expansion': 7200,      # KG扩展缓存2小时
            'medical_association': 3600 # 医疗关联缓存1小时
        }
    }

# 向量存储配置
def get_vector_store_config(config: ProductionConfig) -> Dict[str, Any]:
    """获取向量存储配置"""
    return {
        "max_stores": config.vector_store_cache_size,
        "preload_popular": True,  # 预加载热门向量存储
        "memory_limit_mb": 2048,  # 内存限制2GB
        "cleanup_interval": 300,  # 5分钟清理一次
    }

# CORS配置
def get_cors_config(config: ProductionConfig) -> Dict[str, Any]:
    """获取CORS配置"""
    if not config.enable_cors:
        return {}
    
    return {
        "allow_origins": config.allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
        "max_age": 86400,  # 24小时
    }

# 限流配置
def get_rate_limit_config(config: ProductionConfig) -> Dict[str, Any]:
    """获取限流配置"""
    return {
        "per_minute": config.rate_limit_per_minute,
        "per_hour": config.rate_limit_per_hour,
        "storage_uri": os.getenv("REDIS_URL", "redis://localhost:6379/1"),
        "strategy": "moving-window",
    }

# 监控配置
def get_monitoring_config(config: ProductionConfig) -> Dict[str, Any]:
    """获取监控配置"""
    return {
        "enable_metrics": config.enable_metrics,
        "metrics_port": config.metrics_port,
        "health_check_path": "/health",
        "metrics_path": "/metrics",
        "log_requests": True,
        "log_responses": False,  # 避免敏感信息泄露
    }

# 安全配置
def get_security_config(config: ProductionConfig) -> Dict[str, Any]:
    """获取安全配置"""
    return {
        "max_request_size": config.max_request_size,
        "trusted_hosts": ["*"],  # 生产环境应该限制
        "https_redirect": False,  # 由反向代理处理
        "include_server_header": False,
    }

# 日志配置
def get_logging_config(config: ProductionConfig) -> Dict[str, Any]:
    """获取日志配置"""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "access": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": config.log_level,
            "handlers": ["default"],
        },
        "loggers": {
            "uvicorn.error": {
                "level": config.log_level,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

# 导出配置
__all__ = [
    "ProductionConfig",
    "PRODUCTION_CONFIG",
    "load_from_env",
    "generate_gunicorn_config",
    "get_redis_config",
    "get_cache_config",
    "get_vector_store_config",
    "get_cors_config",
    "get_rate_limit_config",
    "get_monitoring_config",
    "get_security_config",
    "get_logging_config",
]