import asyncio

from sqlalchemy import inspect

from cache_service.infrastructure.database import create_engine, create_tables
from cache_service.infrastructure.models import Base


async def test_replicas_can_create_the_schema_concurrently(engine, settings):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    async def start_replica() -> None:
        replica_engine = create_engine(settings.database_url)  # its own connections, like a pod
        try:
            await create_tables(replica_engine)
        finally:
            await replica_engine.dispose()

    await asyncio.gather(*(start_replica() for _ in range(8)))

    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert set(Base.metadata.tables) <= tables


async def test_create_tables_is_idempotent(engine):
    await create_tables(engine)
    await create_tables(engine)
