"""Central translation of exceptions into HTTP responses.

Routes and services raise domain errors and never build error responses themselves, so every
failure leaves the API in one consistent shape: ``{"detail": "..."}``.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cache_service.domain.errors import (
    DomainError,
    InvalidPayloadError,
    PayloadNotFoundError,
    TransformerError,
)

logger = logging.getLogger(__name__)

# The one place that decides which HTTP status each domain error means.
STATUS_BY_ERROR: dict[type[DomainError], int] = {
    InvalidPayloadError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    PayloadNotFoundError: status.HTTP_404_NOT_FOUND,
    TransformerError: status.HTTP_502_BAD_GATEWAY,
}


async def domain_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Map a domain error to its configured status.

    :param request: Request that caused the error.
    :param error: The domain error.
    :return: JSON response with the error message under ``detail``.
    """
    status_code = STATUS_BY_ERROR[type(error)]
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error("Upstream failure on %s %s", request.method, request.url.path, exc_info=error)
    return JSONResponse({"detail": str(error)}, status_code=status_code)


async def unhandled_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Turn any unexpected exception into a generic 500 without leaking internals.

    :param request: Request that caused the error.
    :param error: The unexpected exception.
    :return: JSON response with a fixed message under ``detail``.
    """
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=error)
    return JSONResponse(
        {"detail": "Internal server error"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install all error handlers on the application.

    :param app: Application to configure.
    """
    for error_type in STATUS_BY_ERROR:
        app.add_exception_handler(error_type, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
