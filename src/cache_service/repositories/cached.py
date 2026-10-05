"""Read-through cache decorators: same interface as the wrapped repository, so the service
can't tell whether a cache is involved."""

from collections.abc import Iterable, Mapping, Sequence

from cache_service.domain.interfaces import Cache, PayloadRepository, StringRepository

STRING_PREFIX = "string:"
PAYLOAD_PREFIX = "payload:"


class CachedStringRepository(StringRepository):
    """Serves transformed strings from the cache and falls back to the wrapped repository."""

    def __init__(self, repository: StringRepository, cache: Cache) -> None:
        """Create the decorator.

        :param repository: Repository that is the source of truth.
        :param cache: Cache placed in front of it.
        """
        self._repository = repository
        self._cache = cache

    @staticmethod
    def _keys(sources: Iterable[str]) -> dict[str, str]:
        """Map each source to its cache key; being a dict, it also drops duplicate sources."""
        return {source: STRING_PREFIX + source for source in sources}

    @classmethod
    def _entries(cls, results: Mapping[str, str]) -> dict[str, str]:
        """Re-key results by cache key, ready to be written to the cache."""
        keys = cls._keys(results)
        return {keys[source]: result for source, result in results.items()}

    async def get_many(self, sources: Sequence[str]) -> dict[str, str]:
        """Read from the cache, then fill the misses from the repository and cache them."""
        keys = self._keys(sources)
        cached = await self._cache.get_many(list(keys.values()))
        found = {source: cached[key] for source, key in keys.items() if key in cached}

        missing = [source for source in keys if source not in found]
        if missing:
            stored = await self._repository.get_many(missing)
            await self._cache.set_many(self._entries(stored))
            found.update(stored)
        return found

    async def save_many(self, results: Mapping[str, str]) -> None:
        """Persist to the repository, then cache."""
        await self._repository.save_many(results)
        await self._cache.set_many(self._entries(results))


class CachedPayloadRepository(PayloadRepository):
    """Serves payloads from the cache and falls back to the wrapped repository."""

    def __init__(self, repository: PayloadRepository, cache: Cache) -> None:
        """Create the decorator.

        :param repository: Repository that is the source of truth.
        :param cache: Cache placed in front of it.
        """
        self._repository = repository
        self._cache = cache

    async def get(self, id_: str) -> str | None:
        """Read from the cache, falling back to the repository and caching what it finds."""
        cached = await self._cache.get(PAYLOAD_PREFIX + id_)
        if cached is not None:
            return cached
        output = await self._repository.get(id_)
        if output is not None:
            await self._cache.set(PAYLOAD_PREFIX + id_, output)
        return output

    async def save(self, id_: str, output: str) -> bool:
        """Persist to the repository, then cache."""
        # Persist first: the cache must never hold something the database doesn't.
        created = await self._repository.save(id_, output)
        await self._cache.set(PAYLOAD_PREFIX + id_, output)
        return created
