from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from redis import Redis

from cache_service.api import router
from cache_service.config import Settings
from cache_service.store import RedisStore
from cache_service.transformer import Transformer, uppercase_transformer


def create_app(
    settings: Settings | None = None,
    transformer: Transformer | None = None,
    redis_client: Redis | None = None,
) -> FastAPI:
    """Build the app; dependencies are injectable so tests avoid real I/O."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.store = RedisStore(client)
        app.state.transformer = transformer or uppercase_transformer
        yield
        client.close()

    app = FastAPI(title="Payload cache", lifespan=lifespan)
    app.include_router(router)
    return app


def run() -> None:
    uvicorn.run("cache_service.main:create_app", factory=True, host="0.0.0.0", port=8000)
