from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from sqlalchemy.engine import make_url

from cache_service.api import router
from cache_service.config import Settings
from cache_service.db import create_db_engine, create_tables
from cache_service.transformer import Transformer, uppercase_transformer


def create_app(settings: Settings | None = None, transformer: Transformer | None = None) -> FastAPI:
    """Build the app; settings and transformer are injectable so tests avoid real I/O."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = make_url(settings.database_url).database
        if database and database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        app.state.engine = create_db_engine(settings.database_url)
        app.state.transformer = transformer or uppercase_transformer
        create_tables(app.state.engine)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Payload cache", lifespan=lifespan)
    app.include_router(router)
    return app


def run() -> None:
    uvicorn.run("cache_service.main:create_app", factory=True, host="0.0.0.0", port=8000)
