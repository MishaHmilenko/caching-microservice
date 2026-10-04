"""Translation of domain errors into HTTP responses."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from cache_service.domain.payload import InvalidPayloadError


async def invalid_payload_handler(request: Request, error: InvalidPayloadError) -> JSONResponse:
    """Report an unusable payload as a 422 response.

    :param request: Request that caused the error.
    :param error: The domain error.
    :return: JSON response with the error message under ``detail``.
    """
    return JSONResponse({"detail": str(error)}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
