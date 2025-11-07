import time
from typing import Tuple, Dict, Any
from app.cache.redis_client import RedisClient


class RateLimitInfo:
    """限流信息类"""
    def __init__(self, limit: int, remaining: int, reset_time: int):
        self.limit = limit
        self.remaining = remaining
        self.reset_time = reset_time


class RateLimiter:
    """限流器（滑动窗口算法）"""
    
    def __init__(self, storage: RedisClient):
        self.storage = storage
    
    async def check(
        self,  
        identifier: str,  
        endpoint: str,  
        limit: int,  
        window: int
    ) -> Tuple[bool, RateLimitInfo]:
        """
        检查是否超出限流
        
        Args:
            identifier: 标识符（IP或用户ID）
            endpoint: API端点
            limit: 限流配额
            window: 时间窗口（秒）
            
        Returns:
            (是否允许, 限流信息)
        """
        # 计算当前窗口和前窗口的时间戳
        current_window = int(time.time()) // window * window
        previous_window = current_window - window
        
        # 获取两个窗口的请求计数
        current_count = await self._get_count(identifier, endpoint, current_window)
        previous_count = await self._get_count(identifier, endpoint, previous_window)
        
        # 计算经过的时间百分比
        elapsed = time.time() - current_window
        percentage = elapsed / window
        
        # 滑动窗口加权计算
        weighted_count = current_count + previous_count * (1 - percentage)
        
        # 判断是否超出限流
        allowed = weighted_count < limit
        
        # 如果允许，增加计数
        if allowed:
            await self._increment(identifier, endpoint, current_window, window * 2)
        
        # 计算剩余配额和重置时间
        remaining = max(0, limit - int(weighted_count) - (1 if allowed else 0))
        reset_time = current_window + window
        
        return allowed, RateLimitInfo(limit=limit, remaining=remaining, reset_time=reset_time)
    
    async def _get_count(self, identifier: str, endpoint: str, window: int) -> int:
        """获取指定窗口的请求计数"""
        key = self._generate_key(identifier, endpoint, window)
        redis = await self.storage.get_redis()
        count = await redis.get(key)
        return int(count) if count is not None else 0
    
    async def _increment(self, identifier: str, endpoint: str, window: int, expire: int) -> None:
        """增加指定窗口的请求计数"""
        key = self._generate_key(identifier, endpoint, window)
        redis = await self.storage.get_redis()
        await redis.incr(key)
        await redis.expire(key, expire)
    
    def _generate_key(self, identifier: str, endpoint: str, window: int) -> str:
        """生成Redis存储键"""
        return f"rate_limit:{identifier}:{endpoint}:{window}"