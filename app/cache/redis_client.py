from redis.asyncio import Redis
from typing import Optional
from app.core.config import get_app_settings


class RedisClient:
    """Redis客户端单例"""
    
    _instance: Optional[Redis] = None
    
    @classmethod
    async def get_redis(cls) -> Redis:
        """获取Redis连接"""
        if cls._instance is None:
            settings = get_app_settings()
            cls._instance = await Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return cls._instance
    
    @classmethod
    async def close_redis(cls):
        """关闭Redis连接"""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None