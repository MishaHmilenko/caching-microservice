"""Transformer implementations."""

from collections.abc import Sequence

from cache_service.domain.interfaces import Transformer


class UppercaseTransformer(Transformer):
    """Simulates the external service by upper-casing every string."""

    async def transform(self, strings: Sequence[str]) -> list[str]:
        """Upper-case each string."""
        return [s.upper() for s in strings]
