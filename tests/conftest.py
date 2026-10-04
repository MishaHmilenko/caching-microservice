"""Test fixtures. Tests run against real Postgres and Redis (see docker-compose.test.yml,
`make test`); only the external transformer is replaced, so calls to it can be counted."""

import os
import socket
import threading
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager

import pytest
import uvicorn
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cache_service.core.config import Settings
from cache_service.domain.interfaces import Transformer
from cache_service.infrastructure.database import create_engine, create_tables
from cache_service.infrastructure.models import Base
from cache_service.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://cache:cache@localhost:5433/cache_test"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0")


class CountingTransformer(Transformer):
    """Records every batch it receives so tests can assert on calls to the 'external service'."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def transform(self, strings: Sequence[str]) -> list[str]:
        self.calls.append(list(strings))
        return [s.upper() for s in strings]


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
    await create_tables(engine)
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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
