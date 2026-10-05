"""HTTP endpoints."""

from fastapi import APIRouter, Response, status

from cache_service.api.dependencies import PayloadServiceDep
from cache_service.api.schemas import ErrorResponse, PayloadCreated, PayloadRequest, PayloadResponse

router = APIRouter()


@router.post(
    "/payload",
    response_model=PayloadCreated,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
    },
)
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


@router.get(
    "/payload/{payload_id}",
    response_model=PayloadResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def read_payload(payload_id: str, service: PayloadServiceDep) -> PayloadResponse:
    """Read a generated payload.

    :param payload_id: Identifier returned when the payload was created.
    :param service: Payload service.
    :return: The payload output.
    :raises PayloadNotFoundError: If the payload does not exist (reported as 404).
    """
    return PayloadResponse(output=await service.get_output(payload_id))


@router.get("/health")
async def health() -> dict[str, str]:
    """Report that the service is up.

    :return: A static status document.
    """
    return {"status": "ok"}
