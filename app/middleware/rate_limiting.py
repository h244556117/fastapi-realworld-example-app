import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from app.core.rate_limiter import RateLimiter
from app.cache.redis_client import RedisClient
from app.core.config import get_app_settings
from typing import Dict, Tuple, Any


class RateLimitConfig:
    """限流配置类"""
    def __init__(self, limit: int, window: int, dimension: str):
        self.limit = limit
        self.window = window
        self.dimension = dimension


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API限流中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.redis_client = RedisClient()
        self.settings = get_app_settings()
        self.rate_limiter = RateLimiter(self.redis_client)
        self.limit_configs = self._load_limit_configs()
    
    def _load_limit_configs(self) -> Dict[str, RateLimitConfig]:
        """加载限流配置"""
        return {
            "/api/users/login": RateLimitConfig(limit=5, window=60, dimension="ip"),  # 5次/分钟，IP维度
            "/api/users": RateLimitConfig(limit=3, window=3600, dimension="ip"),  # 3次/小时，IP维度
            "/api/articles": RateLimitConfig(limit=10, window=3600, dimension="user"),  # 10次/小时，用户维度
            "/api/articles/{slug}/comments": RateLimitConfig(limit=20, window=3600, dimension="user"),  # 20次/小时，用户维度
            "/api/articles/{slug}/favorite": RateLimitConfig(limit=30, window=60, dimension="user"),  # 30次/分钟，用户维度
            "/api/articles": RateLimitConfig(limit=100, window=60, dimension="ip"),  # 100次/分钟，IP维度
            "/api/articles/{slug}": RateLimitConfig(limit=60, window=60, dimension="ip"),  # 60次/分钟，IP维度
            "/api/profiles/{username}": RateLimitConfig(limit=60, window=60, dimension="ip"),  # 60次/分钟，IP维度
        }
    
    def _get_rate_limit_config(self, request: Request) -> RateLimitConfig:
        """获取当前请求的限流配置"""
        path = request.url.path
        
        # 匹配精确路径
        if path in self.limit_configs:
            return self.limit_configs[path]
        
        # 匹配带参数的路径（如/articles/{slug}）
        for pattern, config in self.limit_configs.items():
            if "{" in pattern and "}" in pattern:
                # 简单的参数路径匹配
                pattern_parts = pattern.split("/")
                path_parts = path.split("/")
                
                if len(pattern_parts) == len(path_parts):
                    match = True
                    for i in range(len(pattern_parts)):
                        if pattern_parts[i].startswith("{") and pattern_parts[i].endswith("}"):
                            continue
                        if pattern_parts[i] != path_parts[i]:
                            match = False
                            break
                    if match:
                        return config
        
        # 默认配置：无限制
        return RateLimitConfig(limit=0, window=60, dimension="ip")
    
    def _get_identifier(self, request: Request, config: RateLimitConfig) -> str:
        """获取限流标识符"""
        if config.dimension == "user":
            # 从请求中获取用户ID（需要在认证中间件之后执行）
            user_id = request.state.user.id if hasattr(request.state, "user") and hasattr(request.state.user, "id") else None
            if user_id:
                return f"user:{user_id}"
            # 如果用户未登录，回退到IP维度
            return self._get_ip_identifier(request)
        elif config.dimension == "ip":
            return self._get_ip_identifier(request)
        else:
            # 默认使用IP维度
            return self._get_ip_identifier(request)
    
    def _get_ip_identifier(self, request: Request) -> str:
        """获取IP标识符"""
        # 尝试从X-Forwarded-For头获取真实IP（如果在反向代理后面）
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return f"ip:{x_forwarded_for.split(',')[0].strip()}"
        # 直接获取客户端IP
        return f"ip:{request.client.host}"
    
    def _rate_limit_response(self, retry_after: int) -> JSONResponse:
        """生成限流响应"""
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": retry_after
            }
        )
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        """处理请求"""
        # 跳过对静态文件的限流
        if request.url.path.startswith("/static"):
            return await call_next(request)
        
        # 获取限流配置
        config = self._get_rate_limit_config(request)
        
        # 如果限流配置为0，表示无限制
        if config.limit == 0:
            return await call_next(request)
        
        # 提取标识符
        identifier = self._get_identifier(request, config)
        
        # 检查限流
        allowed, info = await self.rate_limiter.check(
            identifier=identifier,
            endpoint=request.url.path,
            limit=config.limit,
            window=config.window
        )
        
        # 生成响应
        if allowed:
            response = await call_next(request)
        else:
            retry_after = int(info.reset_time - time.time())
            response = self._rate_limit_response(retry_after)
        
        # 添加限流响应头
        response.headers["X-RateLimit-Limit"] = str(info.limit)
        response.headers["X-RateLimit-Remaining"] = str(info.remaining)
        response.headers["X-RateLimit-Reset"] = str(info.reset_time)
        
        return response