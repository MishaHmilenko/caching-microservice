"""Contracts between layers. The service depends only on these, never on Redis or SQL."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence


class Transformer(ABC):
    """Stand-in for the external service. Takes a batch so one call can serve many strings."""

    @abstractmethod
    async def transform(self, strings: Sequence[str]) -> list[str]:
        """Return one result per input, in the same order."""


class Cache(ABC):
    """Best-effort key-value cache; a failing backend must behave like an empty one."""

    @abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abstractmethod
    async def get_many(self, keys: Sequence[str]) -> dict[str, str]:
        """Return only the keys that are present."""

    @abstractmethod
    async def set(self, key: str, value: str) -> None: ...

    @abstractmethod
    async def set_many(self, items: Mapping[str, str]) -> None: ...


class StringRepository(ABC):
    """Persistent store of transformer outcomes, keyed by the input string."""

    @abstractmethod
    async def get_many(self, sources: Sequence[str]) -> dict[str, str]:
        """Return results for the sources that are known; unknown ones are omitted."""

    @abstractmethod
    async def save_many(self, results: Mapping[str, str]) -> None:
        """Store results; keys that already exist are left untouched."""


class PayloadRepository(ABC):
    """Persistent store of generated payloads, keyed by their identifier."""

    @abstractmethod
    async def get(self, id_: str) -> str | None: ...

    @abstractmethod
    async def save(self, id_: str, output: str) -> bool:
        """Store the payload; return False if it already existed."""
