"""Pure payload rules, free of any I/O."""

from collections.abc import Sequence

OUTPUT_SEPARATOR = ", "


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    """Alternate items from two equally long sequences, starting with ``first``.

    :param first: Items taking the odd positions.
    :param second: Items taking the even positions.
    :return: The interleaved items.
    :raises ValueError: If the sequences differ in length.
    """
    return [item for pair in zip(first, second, strict=True) for item in pair]
