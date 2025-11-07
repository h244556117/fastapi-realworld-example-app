from typing import List
from app.cache.redis_client import RedisClient


async def invalidate_cache(patterns: List[str]) -> int:
    """
    失效匹配模式的所有缓存
    
    Args:
        patterns: 缓存键模式列表，支持通配符 *
        
    Returns:
        失效的缓存数量
    """
    redis = await RedisClient.get_redis()
    invalidated_count = 0
    
    for pattern in patterns:
        # 使用SCAN代替KEYS以避免阻塞Redis
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            if keys:
                invalidated_count += await redis.delete(*keys)
            if cursor == 0:
                break
    
    return invalidated_count