"""Errors grouped by business domain, each branch deriving from the application root."""

from cache_service.core.exceptions import BaseError


class PayloadError(BaseError):
    """Base class of errors in the payload domain."""

    status_code = 400
    default_detail = "Payload error"


class InvalidPayloadError(PayloadError, ValueError):
    """The inputs cannot form a payload."""

    status_code = 422
    default_detail = "list_1 and list_2 must have the same length"


class PayloadNotFoundError(PayloadError):
    """No payload exists for the requested identifier."""

    status_code = 404
    default_detail = "Payload not found"


class TransformerError(BaseError):
    """Base class of errors in the external transformer domain."""

    status_code = 502
    default_detail = "Transformer failure"


class TransformerUnavailableError(TransformerError):
    """The transformer could not be reached in time, even after retrying."""

    status_code = 503
    default_detail = "Transformer is unavailable"


class TransformerResponseError(TransformerError):
    """The transformer answered with something unusable."""

    default_detail = "Transformer returned an invalid response"
