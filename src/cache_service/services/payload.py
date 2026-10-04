from collections.abc import Sequence

from cache_service.domain.interfaces import PayloadRepository, StringRepository, Transformer
from cache_service.domain.payload import OUTPUT_SEPARATOR, interleave, payload_id


class PayloadService:
    def __init__(
        self,
        strings: StringRepository,
        payloads: PayloadRepository,
        transformer: Transformer,
    ) -> None:
        self._strings = strings
        self._payloads = payloads
        self._transformer = transformer

    async def get_output(self, id_: str) -> str | None:
        return await self._payloads.get(id_)

    async def create(self, list_1: Sequence[str], list_2: Sequence[str]) -> tuple[str, bool]:
        """Return the payload id and whether it was newly created."""
        id_ = payload_id(list_1, list_2)
        if await self._payloads.get(id_) is not None:
            return id_, False

        results = await self._transform_with_cache([*list_1, *list_2])
        output = OUTPUT_SEPARATOR.join(
            interleave([results[s] for s in list_1], [results[s] for s in list_2])
        )
        created = await self._payloads.save(id_, output)
        return id_, created

    async def _transform_with_cache(self, strings: Sequence[str]) -> dict[str, str]:
        """Map every distinct input to its transformed value, calling the transformer at most
        once, and only for strings that have never been seen."""
        distinct = list(dict.fromkeys(strings))
        results = await self._strings.get_many(distinct)

        missing = [s for s in distinct if s not in results]
        if missing:
            transformed = await self._transformer.transform(missing)
            if len(transformed) != len(missing):
                raise RuntimeError("Transformer returned a different number of results")
            fresh = dict(zip(missing, transformed, strict=True))
            await self._strings.save_many(fresh)
            results.update(fresh)
        return results
