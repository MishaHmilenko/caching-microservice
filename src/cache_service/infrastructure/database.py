from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cache_service.infrastructure.models import Base


def create_engine(url: str) -> AsyncEngine:
    # Validate connections on checkout so a restarted database doesn't surface as errors.
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    # Shortcut: create_all instead of migrations; adopt Alembic once the schema evolves.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
