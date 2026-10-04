"""HTTP endpoints."""

from fastapi import APIRouter, HTTPException, Response, status

from cache_service.api.dependencies import PayloadServiceDep
from cache_service.api.schemas import PayloadCreated, PayloadRequest, PayloadResponse

router = APIRouter()


@router.post("/payload", response_model=PayloadCreated, status_code=status.HTTP_201_CREATED)
async def create_payload(
    body: PayloadRequest, service: PayloadServiceDep, response: Response
) -> PayloadCreated:
    """Create a payload from two lists of strings.

    :param body: The two input lists.
    :param service: Payload service.
    :param response: Response, used to downgrade the status when the payload already existed.
    :return: The payload id and a confirmation message.
    """
    id_, created = await service.create(body.list_1, body.list_2)
    if not created:
        response.status_code = status.HTTP_200_OK
    return PayloadCreated(
        id=id_, message="Payload created" if created else "Payload already exists"
    )


@router.get("/payload/{payload_id}", response_model=PayloadResponse)
async def read_payload(payload_id: str, service: PayloadServiceDep) -> PayloadResponse:
    """Read a generated payload.

    :param payload_id: Identifier returned when the payload was created.
    :param service: Payload service.
    :return: The payload output.
    :raises HTTPException: With status 404 if the payload does not exist.
    """
    output = await service.get_output(payload_id)
    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found")
    return PayloadResponse(output=output)


@router.get("/health")
async def health() -> dict[str, str]:
    """Report that the service is up.

    :return: A static status document.
    """
    return {"status": "ok"}
