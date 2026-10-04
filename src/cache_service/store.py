from collections.abc import Mapping, Sequence

from redis import Redis

PAYLOAD_PREFIX = "payload:"
STRING_PREFIX = "string:"


class RedisStore:
    """Persistence for transformed strings and generated payloads.

    Writes are plain SETs: results are deterministic, so concurrent writers storing the same
    key are harmless and no conflict handling is needed.
    """

    def __init__(self, client: Redis) -> None:
        # decode_responses is required so values come back as str rather than bytes.
        self._client = client

    def get_payload(self, id_: str) -> str | None:
        return self._client.get(PAYLOAD_PREFIX + id_)

    def set_payload(self, id_: str, output: str) -> None:
        self._client.set(PAYLOAD_PREFIX + id_, output)

    def get_strings(self, sources: Sequence[str]) -> dict[str, str]:
        """Return cached results for the sources that are known; unknown ones are omitted."""
        if not sources:
            return {}
        values = self._client.mget([STRING_PREFIX + s for s in sources])
        return {s: v for s, v in zip(sources, values, strict=True) if v is not None}

    def set_strings(self, results: Mapping[str, str]) -> None:
        if not results:
            return
        # One round trip for the whole batch.
        self._client.mset({STRING_PREFIX + s: r for s, r in results.items()})
