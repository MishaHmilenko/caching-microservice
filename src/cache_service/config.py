from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration, overridable through ``CACHE_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="CACHE_")

    # Any SQLAlchemy URL works; SQLite is the default to keep the service self-contained.
    database_url: str = "sqlite:///./data/cache.db"
