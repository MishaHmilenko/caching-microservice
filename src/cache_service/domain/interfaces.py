"""Contracts between layers. The service depends only on these, never on Redis or SQL."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence


class Transformer(ABC):
    """Stand-in for the external service.

    Takes a batch so that one call can serve many strings.
    """

    @abstractmethod
    async def transform(self, strings: Sequence[str]) -> list[str]:
        """Transform a batch of strings.

        :param strings: Strings to transform.
        :return: One result per input, in the same order.
        """


class Cache(ABC):
    """Best-effort key-value cache; a failing backend must behave like an empty one."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Read a single entry.

        :param key: Cache key.
        :return: The cached value, or ``None`` on a miss.
        """

    @abstractmethod
    async def get_many(self, keys: Sequence[str]) -> dict[str, str]:
        """Read several entries at once.

        :param keys: Cache keys.
        :return: Mapping of the keys that are present; misses are omitted.
        """

    @abstractmethod
    async def set(self, key: str, value: str) -> None:
        """Write a single entry.

        :param key: Cache key.
        :param value: Value to store.
        """

    @abstractmethod
    async def set_many(self, items: Mapping[str, str]) -> None:
        """Write several entries at once.

        :param items: Mapping of cache keys to values.
        """


class StringRepository(ABC):
    """Persistent store of transformer outcomes, keyed by the input string."""

    @abstractmethod
    async def get_many(self, sources: Sequence[str]) -> dict[str, str]:
        """Look up previously transformed strings.

        :param sources: Input strings.
        :return: Mapping of source to result for the known sources; unknown ones are omitted.
        """

    @abstractmethod
    async def save_many(self, results: Mapping[str, str]) -> None:
        """Store transformer outcomes; keys that already exist are left untouched.

        :param results: Mapping of source string to its transformed result.
        """


class PayloadRepository(ABC):
    """Persistent store of generated payloads, keyed by their identifier."""

    @abstractmethod
    async def get(self, id_: str) -> str | None:
        """Read a payload.

        :param id_: Payload identifier.
        :return: The payload output, or ``None`` if it does not exist.
        """

    @abstractmethod
    async def save(self, id_: str, output: str) -> bool:
        """Store a payload.

        :param id_: Payload identifier.
        :param output: Generated payload output.
        :return: ``False`` if the payload already existed, ``True`` otherwise.
        """
