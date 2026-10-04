from fastapi import Request, status
from fastapi.responses import JSONResponse

from cache_service.domain.payload import InvalidPayloadError


async def invalid_payload_handler(request: Request, error: InvalidPayloadError) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
