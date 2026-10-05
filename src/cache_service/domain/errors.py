"""Domain errors. They carry no HTTP knowledge; the API layer maps them to responses."""


class DomainError(Exception):
    """Base class of every error the domain raises on purpose."""


class InvalidPayloadError(DomainError, ValueError):
    """The inputs cannot form a payload."""


class PayloadNotFoundError(DomainError):
    """No payload exists for the requested identifier."""


class TransformerError(DomainError):
    """The external transformer misbehaved, e.g. returned an unusable response."""
