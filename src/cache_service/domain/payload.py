"""Pure payload rules, free of any I/O."""

import hashlib
import json
from collections.abc import Sequence

OUTPUT_SEPARATOR = ", "


class InvalidPayloadError(ValueError):
    """The inputs cannot form a payload."""


def validate_lists(list_1: Sequence[str], list_2: Sequence[str]) -> None:
    # Interleaving pairs items up, so a length mismatch would silently drop data.
    if len(list_1) != len(list_2):
        raise InvalidPayloadError("list_1 and list_2 must have the same length")


def payload_id(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Derive the identifier from the inputs so identical requests share one payload."""
    canonical = json.dumps([list(list_1), list(list_2)], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    return [item for pair in zip(first, second, strict=True) for item in pair]
