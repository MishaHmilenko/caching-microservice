"""Service configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration, overridable through ``CACHE_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="CACHE_")

    database_url: str = "postgresql+asyncpg://cache:cache@localhost:5432/cache"
    redis_url: str = "redis://localhost:6379/0"
    # Postgres is the source of truth, so cache entries can safely expire.
    cache_ttl_seconds: int = 3600
    # Spreads expirations so a popular batch of entries does not stampede Postgres at once.
    cache_ttl_jitter: float = 0.1
