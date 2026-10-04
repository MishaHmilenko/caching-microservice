"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Request

from cache_service.services.payload import PayloadService


def get_payload_service(request: Request) -> PayloadService:
    """Provide the payload service built at startup.

    :param request: Current request, used to reach the application state.
    :return: The shared :class:`PayloadService`.
    """
    # Built once at startup (see main.lifespan); tests may override via dependency_overrides.
    return request.app.state.payload_service


PayloadServiceDep = Annotated[PayloadService, Depends(get_payload_service)]
