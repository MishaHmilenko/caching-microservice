import hashlib
import json
from collections.abc import Sequence

from cache_service.store import RedisStore
from cache_service.transformer import Transformer

OUTPUT_SEPARATOR = ", "


def payload_id(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Derive the identifier from the inputs so identical requests share one payload."""
    canonical = json.dumps([list(list_1), list(list_2)], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    return [item for pair in zip(first, second, strict=True) for item in pair]


class PayloadService:
    def __init__(self, store: RedisStore, transformer: Transformer) -> None:
        self._store = store
        self._transformer = transformer

    def get_output(self, id_: str) -> str | None:
        return self._store.get_payload(id_)

    def create(self, list_1: Sequence[str], list_2: Sequence[str]) -> tuple[str, bool]:
        """Return the payload id and whether it was newly created."""
        id_ = payload_id(list_1, list_2)
        if self._store.get_payload(id_) is not None:
            return id_, False

        results = self._transform_with_cache([*list_1, *list_2])
        output = OUTPUT_SEPARATOR.join(
            interleave([results[s] for s in list_1], [results[s] for s in list_2])
        )
        self._store.set_payload(id_, output)
        return id_, True

    def _transform_with_cache(self, strings: Sequence[str]) -> dict[str, str]:
        """Map every distinct input to its transformed value, calling the transformer at most
        once, and only for strings that have never been seen."""
        distinct = list(dict.fromkeys(strings))
        results = self._store.get_strings(distinct)

        missing = [s for s in distinct if s not in results]
        if missing:
            transformed = self._transformer(missing)
            if len(transformed) != len(missing):
                raise RuntimeError("Transformer returned a different number of results")
            fresh = dict(zip(missing, transformed, strict=True))
            self._store.set_strings(fresh)
            results.update(fresh)
        return results
