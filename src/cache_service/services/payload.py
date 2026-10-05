"""Application services implementing the use cases."""

import hashlib
import json
from collections.abc import Sequence

from cache_service.domain.errors import (
    InvalidPayloadError,
    PayloadNotFoundError,
    TransformerResponseError,
)
from cache_service.domain.interfaces import PayloadRepository, StringRepository, Transformer
from cache_service.domain.payload import OUTPUT_SEPARATOR, interleave


class PayloadService:
    """Use cases for creating and reading payloads."""

    def __init__(
        self,
        strings: StringRepository,
        payloads: PayloadRepository,
        transformer: Transformer,
    ) -> None:
        """Create the service.

        :param strings: Store of per-string transformer outcomes.
        :param payloads: Store of generated payloads.
        :param transformer: Client of the external transformer.
        """
        self._strings = strings
        self._payloads = payloads
        self._transformer = transformer

    @staticmethod
    def validate_lists(list_1: Sequence[str], list_2: Sequence[str]) -> None:
        """Check that two lists can be interleaved.

        :param list_1: First list of strings.
        :param list_2: Second list of strings.
        :raises InvalidPayloadError: If the lists differ in length.
        """
        # Interleaving pairs items up, so a length mismatch would silently drop data.
        if len(list_1) != len(list_2):
            raise InvalidPayloadError("list_1 and list_2 must have the same length")

    @staticmethod
    def _payload_id(list_1: Sequence[str], list_2: Sequence[str]) -> str:
        """Derive the identifier from the inputs so identical requests share one payload.

        :param list_1: First list of strings.
        :param list_2: Second list of strings.
        :return: Hex SHA-256 digest of the canonical JSON of both lists.
        """
        canonical = json.dumps(
            [list(list_1), list(list_2)], ensure_ascii=False, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def get_output(self, id_: str) -> str:
        """Read a generated payload.

        :param id_: Payload identifier.
        :return: The payload output.
        :raises PayloadNotFoundError: If no payload exists for the identifier.
        """
        output = await self._payloads.get(id_)
        if output is None:
            raise PayloadNotFoundError(f"Payload {id_} not found")
        return output

    async def create(self, list_1: Sequence[str], list_2: Sequence[str]) -> tuple[str, bool]:
        """Create a payload, reusing cached work wherever possible.

        :param list_1: First list of strings.
        :param list_2: Second list of strings.
        :return: The payload id and whether this call newly created it.
        :raises InvalidPayloadError: If the lists cannot be combined.
        :raises TransformerResponseError: If the transformer returns the wrong number of results.
        """
        self.validate_lists(list_1, list_2)
        id_ = self._payload_id(list_1, list_2)
        if await self._payloads.get(id_) is not None:
            return id_, False

        results = await self._transform_with_cache([*list_1, *list_2])
        output = OUTPUT_SEPARATOR.join(
            interleave([results[s] for s in list_1], [results[s] for s in list_2])
        )
        created = await self._payloads.save(id_, output)
        return id_, created

    async def _transform_with_cache(self, strings: Sequence[str]) -> dict[str, str]:
        """Transform strings, calling the transformer at most once and only for unseen ones.

        :param strings: Input strings, possibly with duplicates.
        :return: Mapping of every distinct input to its transformed value.
        :raises TransformerResponseError: If the transformer returns the wrong number of results.
        """
        distinct = list(dict.fromkeys(strings))
        results = await self._strings.get_many(distinct)

        missing = [s for s in distinct if s not in results]
        if missing:
            transformed = await self._transformer.transform(missing)
            if len(transformed) != len(missing):
                raise TransformerResponseError("Transformer returned a different number of results")
            fresh = dict(zip(missing, transformed, strict=True))
            await self._strings.save_many(fresh)
            results.update(fresh)
        return results
