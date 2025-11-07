import asyncio
import json
from functools import wraps
from typing import Callable, Optional, List, TypeVar, Any
from pydantic import BaseModel
from app.cache.redis_client import RedisClient
from app.cache.monitoring import CacheMonitor
from app.core.config import get_app_settings

T = TypeVar('T')


def cache(
    key_pattern: str,
    ttl: Optional[int] = None,
    invalidate_patterns: List[str] = None
):
    """
    通用缓存装饰器
    
    Args:
        key_pattern: 缓存键模式，支持占位符如 {slug}, {username}
        ttl: 缓存过期时间（秒），默认使用配置的默认值
        invalidate_patterns: 写操作时需要失效的缓存模式列表
    
    Returns:
        装饰后的函数
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            settings = get_app_settings()
            if not settings.cache_enabled:
                return await func(*args, **kwargs)
            
            # 生成缓存键
            cache_key = key_pattern.format(**kwargs)
            
            # 获取Redis连接
            redis = await RedisClient.get_redis()
            
            # 尝试从缓存获取数据
            cached_data = await redis.get(cache_key)
            
            if cached_data:
                # 缓存命中
                CacheMonitor.record_hit()
                
                # 检查返回类型是否为Pydantic模型
                if hasattr(func, '__annotations__') and 'return' in func.__annotations__:
                    return_type = func.__annotations__['return']
                    if isinstance(return_type, type) and issubclass(return_type, BaseModel):
                        return return_type.parse_raw(cached_data)
                    elif hasattr(return_type, '__origin__') and return_type.__origin__ is list:
                        # 处理列表类型
                        item_type = return_type.__args__[0]
                        if issubclass(item_type, BaseModel):
                            return [item_type.parse_raw(item) for item in json.loads(cached_data)]
                
                # 默认情况
                return json.loads(cached_data)
            
            # 缓存未命中
            CacheMonitor.record_miss()
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 缓存结果
            if result is not None:
                # 确定TTL
                cache_ttl = ttl or settings.cache_default_ttl
                
                # 序列化数据
                if isinstance(result, BaseModel):
                    serialized_data = result.json()
                elif isinstance(result, list) and result and isinstance(result[0], BaseModel):
                    serialized_data = json.dumps([item.json() for item in result])
                else:
                    serialized_data = json.dumps(result)
                
                await redis.setex(cache_key, cache_ttl, serialized_data)
            
            return result
        
        # 为函数添加失效模式属性
        if invalidate_patterns:
            wrapper.invalidate_patterns = invalidate_patterns
        
        return wrapper
    
    return decorator