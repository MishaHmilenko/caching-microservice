"""Read-through cache decorators: same interface as the wrapped repository, so the service
can't tell whether a cache is involved."""

from collections.abc import Mapping, Sequence

from cache_service.interfaces import Cache, PayloadRepository, StringRepository

STRING_PREFIX = "string:"
PAYLOAD_PREFIX = "payload:"


class CachedStringRepository(StringRepository):
    def __init__(self, repository: StringRepository, cache: Cache) -> None:
        self._repository = repository
        self._cache = cache

    async def get_many(self, sources: Sequence[str]) -> dict[str, str]:
        cached = await self._cache.get_many([STRING_PREFIX + s for s in sources])
        found = {s: cached[STRING_PREFIX + s] for s in sources if STRING_PREFIX + s in cached}

        missing = [s for s in sources if s not in found]
        if missing:
            stored = await self._repository.get_many(missing)
            await self._cache.set_many({STRING_PREFIX + s: r for s, r in stored.items()})
            found.update(stored)
        return found

    async def save_many(self, results: Mapping[str, str]) -> None:
        await self._repository.save_many(results)
        await self._cache.set_many({STRING_PREFIX + s: r for s, r in results.items()})


class CachedPayloadRepository(PayloadRepository):
    def __init__(self, repository: PayloadRepository, cache: Cache) -> None:
        self._repository = repository
        self._cache = cache

    async def get(self, id_: str) -> str | None:
        cached = await self._cache.get(PAYLOAD_PREFIX + id_)
        if cached is not None:
            return cached
        output = await self._repository.get(id_)
        if output is not None:
            await self._cache.set(PAYLOAD_PREFIX + id_, output)
        return output

    async def save(self, id_: str, output: str) -> bool:
        # Persist first: the cache must never hold something the database doesn't.
        created = await self._repository.save(id_, output)
        await self._cache.set(PAYLOAD_PREFIX + id_, output)
        return created
