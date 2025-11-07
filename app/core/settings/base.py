from enum import Enum

from pydantic_settings import BaseSettings


class AppEnvTypes(Enum):
    prod: str = "prod"
    dev: str = "dev"
    test: str = "test"


class BaseAppSettings(BaseSettings):
    app_env: AppEnvTypes = AppEnvTypes.prod
    redis_url: str = "redis://localhost:6379/0"
    cache_enabled: bool = True
    cache_default_ttl: int = 300  # 默认5分钟

    class Config:
        env_file = ".env"
