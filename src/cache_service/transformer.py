from collections.abc import Sequence
from typing import Protocol


class Transformer(Protocol):
    """Stand-in for the external service; takes a batch so one call can serve many strings."""

    def __call__(self, strings: Sequence[str]) -> list[str]: ...


def uppercase_transformer(strings: Sequence[str]) -> list[str]:
    return [s.upper() for s in strings]
