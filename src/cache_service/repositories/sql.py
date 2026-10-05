"""Postgres implementations of the repository contracts."""

from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cache_service.core.hashing import sha256_hex
from cache_service.domain.interfaces import PayloadRepository, StringRepository
from cache_service.infrastructure.models import PayloadRow, TransformedStringRow


class SqlStringRepository(StringRepository):
    """Each call runs in its own short transaction, so nothing is held open while the
    service waits on the external transformer."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        :param session_factory: Factory of database sessions.
        """
        self._session_factory = session_factory

    async def get_many(self, sources: Sequence[str]) -> dict[str, str]:
        """Look up transformed strings by the digest of their source."""
        if not sources:
            return {}
        by_hash = {sha256_hex(s): s for s in sources}
        async with self._session_factory() as session:
            rows = await session.execute(
                select(TransformedStringRow.source_hash, TransformedStringRow.result).where(
                    TransformedStringRow.source_hash.in_(by_hash)
                )
            )
            return {by_hash[source_hash]: result for source_hash, result in rows}

    async def save_many(self, results: Mapping[str, str]) -> None:
        """Insert results, ignoring keys that another writer already stored."""
        if not results:
            return
        values = [
            {"source_hash": sha256_hex(source), "source": source, "result": result}
            for source, result in results.items()
        ]
        # Results are deterministic, so a concurrent writer storing the same key is harmless.
        statement = insert(TransformedStringRow).values(values).on_conflict_do_nothing()
        async with self._session_factory() as session, session.begin():
            await session.execute(statement)


class SqlPayloadRepository(PayloadRepository):
    """Stores payloads in Postgres, one short transaction per call."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        :param session_factory: Factory of database sessions.
        """
        self._session_factory = session_factory

    async def get(self, id_: str) -> str | None:
        """Read a payload by id."""
        async with self._session_factory() as session:
            return await session.scalar(select(PayloadRow.output).where(PayloadRow.id == id_))

    async def save(self, id_: str, output: str) -> bool:
        """Insert a payload; report whether this call was the one that created it."""
        statement = insert(PayloadRow).values(id=id_, output=output).on_conflict_do_nothing()
        async with self._session_factory() as session, session.begin():
            result = await session.execute(statement)
        return result.rowcount == 1
