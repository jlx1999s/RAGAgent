"""
Redis缓存适配器
提供与现有CacheService完全兼容的Redis缓存实现
支持内存回退机制以确保系统稳定性
"""

import os
import json
import time
import hashlib
import asyncio
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

# 可选Redis支持
try:
    from redis.asyncio import Redis
    _REDIS_AVAILABLE = True
except ImportError:
    Redis = None
    _REDIS_AVAILABLE = False

@dataclass
class CacheEntry:
    """缓存条目（与原版保持一致）"""
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

class RedisCacheAdapter:
    """Redis缓存适配器，与原CacheService接口完全兼容"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._memory_cache: Dict[str, CacheEntry] = {}  # 内存回退缓存
        self._redis: Optional[Redis] = None
        self._redis_available = False
        
        # 不同类型缓存的TTL设置（与原版保持一致）
        self.ttl_config = {
            'query_result': 1800,      # 查询结果缓存30分钟
            'entity_extraction': 3600,  # 实体提取缓存1小时
            'intent_recognition': 1800, # 意图识别缓存30分钟
            'kg_expansion': 7200,      # KG扩展缓存2小时
            'medical_association': 3600 # 医疗关联缓存1小时
        }
        
        # 初始化Redis连接
        self._init_redis()
    
    def _init_redis(self):
        """初始化Redis连接"""
        if not _REDIS_AVAILABLE:
            logger.warning("Redis库未安装，使用内存缓存回退")
            return
        
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._redis = Redis.from_url(redis_url, decode_responses=True)
            self._redis_available = True
            logger.info(f"Redis缓存适配器初始化成功: {redis_url}")
        except Exception as e:
            logger.warning(f"Redis连接失败，使用内存缓存回退: {e}")
            self._redis_available = False
    
    def _generate_key(self, prefix: str, data: Any) -> str:
        """生成缓存键（与原版保持一致）"""
        if isinstance(data, dict):
            # 对字典进行排序以确保一致性
            sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            sorted_data = str(data)
        
        hash_obj = hashlib.md5(sorted_data.encode('utf-8'))
        return f"cache:{prefix}:{hash_obj.hexdigest()}"
    
    async def _redis_get(self, key: str) -> Optional[CacheEntry]:
        """从Redis获取缓存条目"""
        if not self._redis_available or not self._redis:
            return None
        
        try:
            data = await self._redis.get(key)
            if data:
                entry_dict = json.loads(data)
                entry = CacheEntry(**entry_dict)
                if not entry.is_expired():
                    entry.access()
                    # 更新访问计数到Redis
                    entry_dict['access_count'] = entry.access_count
                    await self._redis.set(key, json.dumps(entry_dict, default=str), ex=entry.ttl)
                    return entry
                else:
                    # 删除过期条目
                    await self._redis.delete(key)
            return None
        except Exception as e:
            logger.warning(f"Redis获取失败: {e}")
            return None
    
    async def _redis_set(self, key: str, entry: CacheEntry) -> bool:
        """向Redis设置缓存条目"""
        if not self._redis_available or not self._redis:
            return False
        
        try:
            entry_dict = asdict(entry)
            await self._redis.set(key, json.dumps(entry_dict, default=str), ex=entry.ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis设置失败: {e}")
            return False
    
    async def _redis_delete(self, key: str) -> bool:
        """从Redis删除缓存条目"""
        if not self._redis_available or not self._redis:
            return False
        
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis删除失败: {e}")
            return False
    
    def _cleanup_expired_memory(self):
        """清理内存中的过期缓存"""
        expired_keys = []
        for key, entry in self._memory_cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._memory_cache[key]
        
        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 个过期内存缓存条目")
    
    def _evict_lru_memory(self):
        """内存缓存LRU淘汰策略"""
        if len(self._memory_cache) >= self.max_size:
            # 按访问次数和时间排序，淘汰最少使用的
            sorted_items = sorted(
                self._memory_cache.items(),
                key=lambda x: (x[1].access_count, x[1].timestamp)
            )
            
            # 淘汰前10%的条目
            evict_count = max(1, len(sorted_items) // 10)
            for i in range(evict_count):
                key = sorted_items[i][0]
                del self._memory_cache[key]
            
            logger.debug(f"内存缓存LRU淘汰了 {evict_count} 个条目")
    
    def _sync_redis_operation(self, async_func, *args, **kwargs):
        """同步执行异步Redis操作"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建新的线程来执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, async_func(*args, **kwargs))
                    return future.result(timeout=5.0)
            else:
                return loop.run_until_complete(async_func(*args, **kwargs))
        except Exception as e:
            logger.warning(f"Redis操作失败，使用内存缓存: {e}")
            return None
    
    def get(self, cache_type: str, key_data: Any) -> Optional[Any]:
        """获取缓存（同步接口，与原版兼容）"""
        # 使用asyncio.run来处理异步操作，保持同步接口
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在事件循环中，创建任务
                task = asyncio.create_task(self._async_get(cache_type, key_data))
                # 由于我们在同步方法中，需要特殊处理
                return self._sync_get_fallback(cache_type, key_data)
            else:
                return asyncio.run(self._async_get(cache_type, key_data))
        except Exception:
            # 如果异步操作失败，回退到内存缓存
            return self._sync_get_fallback(cache_type, key_data)
    
    async def _async_get(self, cache_type: str, key_data: Any) -> Optional[Any]:
        """异步获取缓存"""
        key = self._generate_key(cache_type, key_data)
        
        # 首先尝试从Redis获取
        entry = await self._redis_get(key)
        if entry:
            logger.debug(f"Redis缓存命中: {cache_type}")
            return entry.data
        
        # Redis未命中，尝试内存缓存
        return self._sync_get_fallback(cache_type, key_data)
    
    def _sync_get_fallback(self, cache_type: str, key_data: Any) -> Optional[Any]:
        """同步内存缓存回退"""
        key = self._generate_key(cache_type, key_data)
        
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if not entry.is_expired():
                entry.access()
                logger.debug(f"内存缓存命中: {cache_type}")
                return entry.data
            else:
                # 删除过期条目
                del self._memory_cache[key]
                logger.debug(f"内存缓存过期: {cache_type}")
        
        return None
    
    def set(self, cache_type: str, key_data: Any, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存（同步接口，与原版兼容）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在事件循环中，创建任务但不等待
                asyncio.create_task(self._async_set(cache_type, key_data, value, ttl))
            else:
                asyncio.run(self._async_set(cache_type, key_data, value, ttl))
        except Exception:
            # 如果异步操作失败，回退到内存缓存
            pass
        
        # 同时设置内存缓存作为回退
        self._sync_set_fallback(cache_type, key_data, value, ttl)
    
    async def _async_set(self, cache_type: str, key_data: Any, value: Any, ttl: Optional[int] = None) -> None:
        """异步设置缓存"""
        key = self._generate_key(cache_type, key_data)
        ttl = ttl or self.ttl_config.get(cache_type, self.default_ttl)
        
        entry = CacheEntry(
            data=value,
            timestamp=time.time(),
            ttl=ttl
        )
        
        # 尝试设置到Redis
        success = await self._redis_set(key, entry)
        if success:
            logger.debug(f"Redis缓存设置: {cache_type}, TTL: {ttl}s")
    
    def _sync_set_fallback(self, cache_type: str, key_data: Any, value: Any, ttl: Optional[int] = None) -> None:
        """同步内存缓存回退设置"""
        # 定期清理过期缓存
        if len(self._memory_cache) % 100 == 0:
            self._cleanup_expired_memory()
        
        # 检查是否需要淘汰
        self._evict_lru_memory()
        
        key = self._generate_key(cache_type, key_data)
        ttl = ttl or self.ttl_config.get(cache_type, self.default_ttl)
        
        entry = CacheEntry(
            data=value,
            timestamp=time.time(),
            ttl=ttl
        )
        
        self._memory_cache[key] = entry
        logger.debug(f"内存缓存设置: {cache_type}, TTL: {ttl}s")
    
    def invalidate(self, cache_type: str, key_data: Any = None) -> None:
        """失效缓存（与原版兼容）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._async_invalidate(cache_type, key_data))
            else:
                asyncio.run(self._async_invalidate(cache_type, key_data))
        except Exception:
            pass
        
        # 同时清理内存缓存
        self._sync_invalidate_fallback(cache_type, key_data)
    
    async def _async_invalidate(self, cache_type: str, key_data: Any = None) -> None:
        """异步失效缓存"""
        if key_data is None:
            # 失效所有该类型的缓存 - Redis中需要扫描键
            if self._redis_available and self._redis:
                try:
                    pattern = f"cache:{cache_type}:*"
                    keys = []
                    async for key in self._redis.scan_iter(match=pattern):
                        keys.append(key)
                    if keys:
                        await self._redis.delete(*keys)
                        logger.debug(f"Redis失效所有 {cache_type} 缓存")
                except Exception as e:
                    logger.warning(f"Redis批量删除失败: {e}")
        else:
            key = self._generate_key(cache_type, key_data)
            await self._redis_delete(key)
    
    def _sync_invalidate_fallback(self, cache_type: str, key_data: Any = None) -> None:
        """同步内存缓存失效回退"""
        if key_data is None:
            # 失效所有该类型的缓存
            keys_to_remove = [k for k in self._memory_cache.keys() if k.startswith(f"cache:{cache_type}:")]
            for key in keys_to_remove:
                del self._memory_cache[key]
            logger.debug(f"内存失效所有 {cache_type} 缓存")
        else:
            key = self._generate_key(cache_type, key_data)
            if key in self._memory_cache:
                del self._memory_cache[key]
                logger.debug(f"内存失效缓存: {cache_type}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息（与原版兼容）"""
        # 内存缓存统计
        memory_total = len(self._memory_cache)
        memory_expired = sum(1 for entry in self._memory_cache.values() if entry.is_expired())
        
        memory_type_stats = {}
        for key, entry in self._memory_cache.items():
            cache_type = key.split(':')[1] if ':' in key else 'unknown'
            if cache_type not in memory_type_stats:
                memory_type_stats[cache_type] = {'count': 0, 'total_access': 0}
            memory_type_stats[cache_type]['count'] += 1
            memory_type_stats[cache_type]['total_access'] += entry.access_count
        
        stats = {
            'total_entries': memory_total,
            'expired_count': memory_expired,
            'max_size': self.max_size,
            'type_stats': memory_type_stats,
            'redis_available': self._redis_available,
            'cache_backend': 'redis+memory' if self._redis_available else 'memory_only'
        }
        
        return stats
    
    def clear(self) -> None:
        """清空所有缓存（与原版兼容）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._async_clear())
            else:
                asyncio.run(self._async_clear())
        except Exception:
            pass
        
        # 清空内存缓存
        self._memory_cache.clear()
        logger.info("清空所有缓存")
    
    async def _async_clear(self) -> None:
        """异步清空Redis缓存"""
        if self._redis_available and self._redis:
            try:
                # 删除所有cache:*键
                keys = []
                async for key in self._redis.scan_iter(match="cache:*"):
                    keys.append(key)
                if keys:
                    await self._redis.delete(*keys)
                    logger.info("清空Redis缓存")
            except Exception as e:
                logger.warning(f"清空Redis缓存失败: {e}")