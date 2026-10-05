"""Translation of exceptions into HTTP responses.

Routes and services raise errors and never build error responses themselves, so every failure
leaves the API in one consistent shape: ``{"detail": "..."}``.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cache_service.core.exceptions import BaseError

logger = logging.getLogger(__name__)


async def base_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Answer any application error with the status declared on its class.

    :param request: Request that caused the error.
    :param error: The application error; must be a :class:`BaseError`.
    :return: JSON response with the error message under ``detail``.
    """
    assert isinstance(error, BaseError)
    if error.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error("Failure on %s %s", request.method, request.url.path, exc_info=error)
    return JSONResponse({"detail": error.detail}, status_code=error.status_code)


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
    """Install the error handlers on the application.

    :param app: Application to configure.
    """
    # Starlette picks the handler by walking the exception's MRO, so this one covers every
    # subclass of BaseError.
    app.add_exception_handler(BaseError, base_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
