"""Pure payload rules, free of any I/O."""

import hashlib
import json
from collections.abc import Sequence

OUTPUT_SEPARATOR = ", "


class InvalidPayloadError(ValueError):
    """The inputs cannot form a payload."""


def validate_lists(list_1: Sequence[str], list_2: Sequence[str]) -> None:
    """Check that two lists can be interleaved.

    :param list_1: First list of strings.
    :param list_2: Second list of strings.
    :raises InvalidPayloadError: If the lists differ in length.
    """
    # Interleaving pairs items up, so a length mismatch would silently drop data.
    if len(list_1) != len(list_2):
        raise InvalidPayloadError("list_1 and list_2 must have the same length")


def payload_id(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Derive the identifier from the inputs so identical requests share one payload.

    :param list_1: First list of strings.
    :param list_2: Second list of strings.
    :return: Hex SHA-256 digest of the canonical JSON of both lists.
    """
    canonical = json.dumps([list(list_1), list(list_2)], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    """Alternate items from two equally long sequences, starting with ``first``.

    :param first: Items taking the odd positions.
    :param second: Items taking the even positions.
    :return: The interleaved items.
    :raises ValueError: If the sequences differ in length.
    """
    return [item for pair in zip(first, second, strict=True) for item in pair]
