"""Test doubles."""

from collections.abc import Sequence

from cache_service.domain.interfaces import Transformer


class CountingTransformer(Transformer):
    """Records every batch it receives so tests can assert on calls to the 'external service'."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def transform(self, strings: Sequence[str]) -> list[str]:
        self.calls.append(list(strings))
        return [s.upper() for s in strings]
