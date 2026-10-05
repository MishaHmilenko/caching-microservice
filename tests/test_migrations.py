"""The schema is owned by Alembic; these tests keep migrations and models honest.

They are synchronous because Alembic drives its own event loop.
"""

import asyncio

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from cache_service.infrastructure.models import Base
from conftest import TEST_DATABASE_URL, alembic_config


def run_on_connection(function):
    """Run a synchronous inspection function against the test database."""

    async def run():
        engine = create_async_engine(TEST_DATABASE_URL)
        try:
            async with engine.connect() as connection:
                return await connection.run_sync(function)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_upgrade_creates_the_tables_and_downgrade_removes_them():
    config = alembic_config(TEST_DATABASE_URL)
    try:
        command.downgrade(config, "base")
        assert not set(Base.metadata.tables) & run_on_connection(
            lambda c: set(inspect(c).get_table_names())
        )

        command.upgrade(config, "head")
        assert set(Base.metadata.tables) <= run_on_connection(
            lambda c: set(inspect(c).get_table_names())
        )
    finally:
        command.upgrade(config, "head")  # leave the shared database ready for other tests


def test_models_have_no_unmigrated_changes():
    """Fails when a model is edited without a migration, which autogenerate would reveal."""
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")

    diff = run_on_connection(
        lambda c: compare_metadata(
            MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata
        )
    )

    assert diff == []
