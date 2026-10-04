from collections.abc import Sequence

from cache_service.domain.interfaces import Transformer


class UppercaseTransformer(Transformer):
    async def transform(self, strings: Sequence[str]) -> list[str]:
        return [s.upper() for s in strings]
