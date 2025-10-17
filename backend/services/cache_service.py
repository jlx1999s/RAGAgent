"""
缓存服务模块
提供查询结果缓存、实体提取缓存和意图识别缓存功能
"""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

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
    """缓存服务"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        
        # 不同类型缓存的TTL设置
        self.ttl_config = {
            'query_result': 1800,      # 查询结果缓存30分钟
            'entity_extraction': 3600,  # 实体提取缓存1小时
            'intent_recognition': 1800, # 意图识别缓存30分钟
            'kg_expansion': 7200,      # KG扩展缓存2小时
            'medical_association': 3600 # 医疗关联缓存1小时
        }
    
    def _generate_key(self, prefix: str, data: Any) -> str:
        """生成缓存键"""
        if isinstance(data, dict):
            # 对字典进行排序以确保一致性
            sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            sorted_data = str(data)
        
        hash_obj = hashlib.md5(sorted_data.encode('utf-8'))
        return f"{prefix}:{hash_obj.hexdigest()}"
    
    def _cleanup_expired(self):
        """清理过期缓存"""
        expired_keys = []
        for key, entry in self._cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        logger.debug(f"清理了 {len(expired_keys)} 个过期缓存条目")
    
    def _evict_lru(self):
        """LRU淘汰策略"""
        if len(self._cache) >= self.max_size:
            # 按访问次数和时间排序，淘汰最少使用的
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: (x[1].access_count, x[1].timestamp)
            )
            
            # 淘汰前10%的条目
            evict_count = max(1, len(sorted_items) // 10)
            for i in range(evict_count):
                key = sorted_items[i][0]
                del self._cache[key]
            
            logger.debug(f"LRU淘汰了 {evict_count} 个缓存条目")
    
    def get(self, cache_type: str, key_data: Any) -> Optional[Any]:
        """获取缓存"""
        key = self._generate_key(cache_type, key_data)
        
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired():
                entry.access()
                logger.debug(f"缓存命中: {cache_type}")
                return entry.data
            else:
                # 删除过期条目
                del self._cache[key]
                logger.debug(f"缓存过期: {cache_type}")
        
        return None
    
    def set(self, cache_type: str, key_data: Any, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        # 定期清理过期缓存
        if len(self._cache) % 100 == 0:
            self._cleanup_expired()
        
        # 检查是否需要淘汰
        self._evict_lru()
        
        key = self._generate_key(cache_type, key_data)
        ttl = ttl or self.ttl_config.get(cache_type, self.default_ttl)
        
        entry = CacheEntry(
            data=value,
            timestamp=time.time(),
            ttl=ttl
        )
        
        self._cache[key] = entry
        logger.debug(f"缓存设置: {cache_type}, TTL: {ttl}s")
    
    def invalidate(self, cache_type: str, key_data: Any = None) -> None:
        """失效缓存"""
        if key_data is None:
            # 失效所有该类型的缓存
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{cache_type}:")]
            for key in keys_to_remove:
                del self._cache[key]
            logger.debug(f"失效所有 {cache_type} 缓存")
        else:
            key = self._generate_key(cache_type, key_data)
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"失效缓存: {cache_type}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_entries = len(self._cache)
        expired_count = sum(1 for entry in self._cache.values() if entry.is_expired())
        
        type_stats = {}
        for key, entry in self._cache.items():
            cache_type = key.split(':')[0]
            if cache_type not in type_stats:
                type_stats[cache_type] = {'count': 0, 'total_access': 0}
            type_stats[cache_type]['count'] += 1
            type_stats[cache_type]['total_access'] += entry.access_count
        
        return {
            'total_entries': total_entries,
            'expired_count': expired_count,
            'max_size': self.max_size,
            'type_stats': type_stats
        }
    
    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        logger.info("清空所有缓存")

# 全局缓存实例
cache_service = CacheService()