"""Pure payload rules, free of any I/O."""

import hashlib
import json
from collections.abc import Sequence

OUTPUT_SEPARATOR = ", "


def payload_id(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Derive the identifier from the inputs so identical requests share one payload."""
    canonical = json.dumps([list(list_1), list(list_2)], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    return [item for pair in zip(first, second, strict=True) for item in pair]
