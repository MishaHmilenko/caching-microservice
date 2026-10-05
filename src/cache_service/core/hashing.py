"""Hashing shared by the storage layers."""

import hashlib


def sha256_hex(text: str) -> str:
    """Return the hex SHA-256 digest of a string.

    Used to turn arbitrarily long, multibyte text into a fixed-size key.

    :param text: Text to hash (encoded as UTF-8).
    :return: 64 lowercase hex characters.
    """
    return hashlib.sha256(text.encode()).hexdigest()
