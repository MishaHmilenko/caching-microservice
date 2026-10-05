"""Test fixtures. Tests run against real Postgres and Redis (see docker-compose.test.yml,
`make test`); only the external transformer is replaced, so calls to it can be counted."""

import os
import socket
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import uvicorn
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cache_service.core.config import Settings
from cache_service.domain.interfaces import Transformer
from cache_service.infrastructure.database import create_engine
from cache_service.infrastructure.models import Base
from cache_service.main import create_app
from fakes import CountingTransformer

ROOT = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://cache:cache@localhost:5433/cache_test"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0")


def alembic_config(database_url: str) -> Config:
    """Alembic configuration pointed at the given database, silent towards pytest's logging."""
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Bring the test database to the latest schema once, exactly as a deployment would."""
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url=TEST_DATABASE_URL, redis_url=TEST_REDIS_URL)


@pytest.fixture
async def engine(settings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(settings.database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def redis(settings) -> AsyncIterator[Redis]:
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
async def clean_state(engine, redis) -> None:
    """Every test starts from an empty database and cache."""
    async with engine.begin() as connection:
        tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
        await connection.execute(text(f"TRUNCATE {tables}"))
    await redis.flushdb()


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()


@asynccontextmanager
async def running_client(
    settings: Settings, transformer: Transformer | None = None
) -> AsyncIterator[AsyncClient]:
    """An in-process app with its real lifespan (DB + Redis connections) and an HTTP client."""
    app = create_app(settings, transformer)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            yield client


@pytest.fixture
def client_factory(settings):
    """Build extra app instances on the same backing services (restarts, other replicas)."""
    return lambda transformer=None, **overrides: running_client(
        settings.model_copy(update=overrides), transformer
    )


@pytest.fixture
async def client(client_factory, transformer) -> AsyncIterator[AsyncClient]:
    async with client_factory(transformer) as client:
        yield client


@pytest.fixture
def live_server_url(settings) -> Iterator[str]:
    """A real HTTP server for tests of the CLI, which speaks to the service over the network."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("Test server did not start")
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)
