from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration, overridable through ``CACHE_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="CACHE_")

    redis_url: str = "redis://localhost:6379/0"
