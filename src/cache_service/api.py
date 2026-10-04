from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from cache_service.schemas import PayloadCreated, PayloadRequest, PayloadResponse
from cache_service.service import PayloadService

router = APIRouter()


def get_service(request: Request) -> PayloadService:
    return PayloadService(request.app.state.store, request.app.state.transformer)


ServiceDep = Annotated[PayloadService, Depends(get_service)]


@router.post("/payload", response_model=PayloadCreated, status_code=status.HTTP_201_CREATED)
def create_payload(body: PayloadRequest, service: ServiceDep, response: Response):
    id_, created = service.create(body.list_1, body.list_2)
    if not created:
        response.status_code = status.HTTP_200_OK
    return PayloadCreated(
        id=id_, message="Payload created" if created else "Payload already exists"
    )


@router.get("/payload/{payload_id}", response_model=PayloadResponse)
def read_payload(payload_id: str, service: ServiceDep):
    output = service.get_output(payload_id)
    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found")
    return PayloadResponse(output=output)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
