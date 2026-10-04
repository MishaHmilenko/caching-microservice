"""Database engine, session and schema setup."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cache_service.infrastructure.models import Base


def create_engine(url: str) -> AsyncEngine:
    """Create the async engine.

    :param url: SQLAlchemy database URL (an async driver such as ``postgresql+asyncpg``).
    :return: The engine; the caller owns it and must dispose of it.
    """
    # Validate connections on checkout so a restarted database doesn't surface as errors.
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a factory of sessions bound to the engine.

    :param engine: Engine the sessions run on.
    :return: A session factory whose sessions keep loaded objects usable after commit.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    """Create any missing tables.

    :param engine: Engine of the target database.
    """
    # Shortcut: create_all instead of migrations; adopt Alembic once the schema evolves.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
