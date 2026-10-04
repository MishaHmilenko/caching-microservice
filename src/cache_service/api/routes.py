from fastapi import APIRouter, HTTPException, Response, status

from cache_service.api.dependencies import PayloadServiceDep
from cache_service.api.schemas import PayloadCreated, PayloadRequest, PayloadResponse

router = APIRouter()


@router.post("/payload", response_model=PayloadCreated, status_code=status.HTTP_201_CREATED)
async def create_payload(
    body: PayloadRequest, service: PayloadServiceDep, response: Response
) -> PayloadCreated:
    id_, created = await service.create(body.list_1, body.list_2)
    if not created:
        response.status_code = status.HTTP_200_OK
    return PayloadCreated(
        id=id_, message="Payload created" if created else "Payload already exists"
    )


@router.get("/payload/{payload_id}", response_model=PayloadResponse)
async def read_payload(payload_id: str, service: PayloadServiceDep) -> PayloadResponse:
    output = await service.get_output(payload_id)
    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found")
    return PayloadResponse(output=output)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
