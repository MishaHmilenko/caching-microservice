"""Application entry point and composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from redis.asyncio import Redis

from cache_service.api.errors import register_exception_handlers
from cache_service.api.routes import router
from cache_service.core.config import Settings
from cache_service.domain.interfaces import Transformer
from cache_service.infrastructure.database import (
    create_engine,
    create_session_factory,
    create_tables,
)
from cache_service.infrastructure.redis_cache import RedisCache
from cache_service.infrastructure.resilient_transformer import ResilientTransformer
from cache_service.infrastructure.transformer import UppercaseTransformer
from cache_service.repositories.cached import CachedPayloadRepository, CachedStringRepository
from cache_service.repositories.sql import SqlPayloadRepository, SqlStringRepository
from cache_service.services.payload import PayloadService


def create_app(settings: Settings | None = None, transformer: Transformer | None = None) -> FastAPI:
    """Build the application.

    This is the composition root: the only place that knows which implementations back the
    interfaces.

    :param settings: Configuration; read from the environment when omitted.
    :param transformer: Transformer client; the upper-casing stand-in when omitted.
    :return: The configured FastAPI application.
    """
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Open the database and Redis connections for the lifetime of the app."""
        engine = create_engine(settings.database_url)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await create_tables(engine)

        session_factory = create_session_factory(engine)
        cache = RedisCache(redis, settings.cache_ttl_seconds, settings.cache_ttl_jitter)
        app.state.payload_service = PayloadService(
            strings=CachedStringRepository(SqlStringRepository(session_factory), cache),
            payloads=CachedPayloadRepository(SqlPayloadRepository(session_factory), cache),
            transformer=ResilientTransformer(
                transformer or UppercaseTransformer(),
                timeout_seconds=settings.transformer_timeout_seconds,
                max_attempts=settings.transformer_max_attempts,
                backoff_seconds=settings.transformer_backoff_seconds,
                max_concurrency=settings.transformer_max_concurrency,
                batch_size=settings.transformer_batch_size,
            ),
        )
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Payload cache", lifespan=lifespan)
    app.include_router(router)
    register_exception_handlers(app)
    return app


def run() -> None:
    """Serve the application with uvicorn (the ``cache-service`` script)."""
    uvicorn.run("cache_service.main:create_app", factory=True, host="0.0.0.0", port=8000)
