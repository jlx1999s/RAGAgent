"""
缓存服务模块
提供查询结果缓存、实体提取缓存和意图识别缓存功能
支持Redis缓存和内存回退机制
"""

import os
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

# 尝试导入Redis缓存适配器
try:
    from .redis_cache_adapter import RedisCacheAdapter
    _REDIS_ADAPTER_AVAILABLE = True
except ImportError:
    RedisCacheAdapter = None
    _REDIS_ADAPTER_AVAILABLE = False

@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: float
    ttl: int  # 生存时间（秒）
    access_count: int = 0
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > self.ttl
    
    def access(self):
        """记录访问"""
        self.access_count += 1

class CacheService:
    """缓存服务 - 支持Redis和内存缓存"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600, use_redis: bool = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        # 不同类型缓存的TTL设置
        self.ttl_config = {
            'query_result': 1800,      # 查询结果缓存30分钟
            'entity_extraction': 3600,  # 实体提取缓存1小时
            'intent_recognition': 1800, # 意图识别缓存30分钟
            'kg_expansion': 7200,      # KG扩展缓存2小时
            'medical_association': 3600 # 医疗关联缓存1小时
        }
        
        # 决定使用哪种缓存实现
        if use_redis is None:
            # 自动检测：如果环境变量中有REDIS_URL或者有Redis适配器，则使用Redis
            use_redis = bool(os.getenv("REDIS_URL")) and _REDIS_ADAPTER_AVAILABLE
        
        if use_redis and _REDIS_ADAPTER_AVAILABLE:
            logger.info("使用Redis缓存适配器")
            self._cache_impl = RedisCacheAdapter(max_size, default_ttl)
            self._cache_impl.ttl_config = self.ttl_config  # 同步TTL配置
        else:
            logger.info("使用内存缓存实现")
            self._cache_impl = self._create_memory_cache()
    
    def _create_memory_cache(self):
        """创建内存缓存实现（原有逻辑）"""
        memory_cache = type('MemoryCache', (), {})()
        memory_cache._cache = {}
        memory_cache.max_size = self.max_size
        memory_cache.default_ttl = self.default_ttl
        memory_cache.ttl_config = self.ttl_config
        
        # 绑定原有的方法
        memory_cache._generate_key = self._generate_key
        memory_cache._cleanup_expired = self._cleanup_expired
        memory_cache._evict_lru = self._evict_lru
        memory_cache.get = self._memory_get
        memory_cache.set = self._memory_set
        memory_cache.invalidate = self._memory_invalidate
        memory_cache.get_stats = self._memory_get_stats
        memory_cache.clear = self._memory_clear
        
        return memory_cache
    
    def _generate_key(self, prefix: str, data: Any) -> str:
        """生成缓存键"""
        if isinstance(data, dict):
            # 对字典进行排序以确保一致性
            sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            sorted_data = str(data)
        
        hash_obj = hashlib.md5(sorted_data.encode('utf-8'))
        return f"{prefix}:{hash_obj.hexdigest()}"
    
    def _cleanup_expired(self, cache_dict):
        """清理过期缓存"""
        expired_keys = []
        for key, entry in cache_dict.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del cache_dict[key]
        
        logger.debug(f"清理了 {len(expired_keys)} 个过期缓存条目")
    
    def _evict_lru(self, cache_dict, max_size):
        """LRU淘汰策略"""
        if len(cache_dict) >= max_size:
            # 按访问次数和时间排序，淘汰最少使用的
            sorted_items = sorted(
                cache_dict.items(),
                key=lambda x: (x[1].access_count, x[1].timestamp)
            )
            
            # 淘汰前10%的条目
            evict_count = max(1, len(sorted_items) // 10)
            for i in range(evict_count):
                key = sorted_items[i][0]
                del cache_dict[key]
            
            logger.debug(f"LRU淘汰了 {evict_count} 个缓存条目")
    
    # 内存缓存方法（原有逻辑）
    def _memory_get(self, cache_type: str, key_data: Any) -> Optional[Any]:
        """内存缓存获取"""
        key = self._generate_key(cache_type, key_data)
        
        if key in self._cache_impl._cache:
            entry = self._cache_impl._cache[key]
            if not entry.is_expired():
                entry.access()
                logger.debug(f"缓存命中: {cache_type}")
                return entry.data
            else:
                # 删除过期条目
                del self._cache_impl._cache[key]
                logger.debug(f"缓存过期: {cache_type}")
        
        return None
    
    def _memory_set(self, cache_type: str, key_data: Any, value: Any, ttl: Optional[int] = None) -> None:
        """内存缓存设置"""
        # 定期清理过期缓存
        if len(self._cache_impl._cache) % 100 == 0:
            self._cleanup_expired(self._cache_impl._cache)
        
        # 检查是否需要淘汰
        self._evict_lru(self._cache_impl._cache, self._cache_impl.max_size)
        
        key = self._generate_key(cache_type, key_data)
        ttl = ttl or self._cache_impl.ttl_config.get(cache_type, self._cache_impl.default_ttl)
        
        entry = CacheEntry(
            data=value,
            timestamp=time.time(),
            ttl=ttl
        )
        
        self._cache_impl._cache[key] = entry
        logger.debug(f"缓存设置: {cache_type}, TTL: {ttl}s")
    
    def _memory_invalidate(self, cache_type: str, key_data: Any = None) -> None:
        """内存缓存失效"""
        if key_data is None:
            # 失效所有该类型的缓存
            keys_to_remove = [k for k in self._cache_impl._cache.keys() if k.startswith(f"{cache_type}:")]
            for key in keys_to_remove:
                del self._cache_impl._cache[key]
            logger.debug(f"失效所有 {cache_type} 缓存")
        else:
            key = self._generate_key(cache_type, key_data)
            if key in self._cache_impl._cache:
                del self._cache_impl._cache[key]
                logger.debug(f"失效缓存: {cache_type}")
    
    def _memory_get_stats(self) -> Dict[str, Any]:
        """内存缓存统计信息"""
        total_entries = len(self._cache_impl._cache)
        expired_count = sum(1 for entry in self._cache_impl._cache.values() if entry.is_expired())
        
        type_stats = {}
        for key, entry in self._cache_impl._cache.items():
            cache_type = key.split(':')[0]
            if cache_type not in type_stats:
                type_stats[cache_type] = {'count': 0, 'total_access': 0}
            type_stats[cache_type]['count'] += 1
            type_stats[cache_type]['total_access'] += entry.access_count
        
        return {
            'total_entries': total_entries,
            'expired_count': expired_count,
            'max_size': self._cache_impl.max_size,
            'type_stats': type_stats,
            'cache_backend': 'memory_only'
        }
    
    def _memory_clear(self) -> None:
        """内存缓存清空"""
        self._cache_impl._cache.clear()
        logger.info("清空所有缓存")
    
    # 公共接口方法（委托给具体实现）
    def get(self, cache_type: str, key_data: Any) -> Optional[Any]:
        """获取缓存"""
        return self._cache_impl.get(cache_type, key_data)
    
    def set(self, cache_type: str, key_data: Any, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        return self._cache_impl.set(cache_type, key_data, value, ttl)
    
    def invalidate(self, cache_type: str, key_data: Any = None) -> None:
        """失效缓存"""
        return self._cache_impl.invalidate(cache_type, key_data)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self._cache_impl.get_stats()
    
    def clear(self) -> None:
        """清空所有缓存"""
        return self._cache_impl.clear()

# 全局缓存实例
cache_service = CacheService()