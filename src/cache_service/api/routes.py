"""HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Header, Path, Response, status

from cache_service.api.dependencies import PayloadServiceDep
from cache_service.api.schemas import ErrorResponse, PayloadCreated, PayloadRequest, PayloadResponse

router = APIRouter()

# Ids are SHA-256 digests, so anything else cannot exist; rejecting it here keeps junk lookups
# away from Redis and Postgres.
PayloadId = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]

# A payload never changes for a given id (the id is a digest of its inputs), so clients and
# shared caches may keep it forever.
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    """Tell whether a conditional request already holds the current representation.

    :param if_none_match: Raw ``If-None-Match`` header value, if any.
    :param etag: Strong ETag of the current representation.
    :return: ``True`` if the client's validators include it (weak comparison, per RFC 9110).
    """
    if if_none_match is None:
        return False
    candidates = {tag.strip().removeprefix("W/") for tag in if_none_match.split(",")}
    return "*" in candidates or etag in candidates


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
async def read_payload(
    payload_id: PayloadId,
    service: PayloadServiceDep,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
) -> PayloadResponse | Response:
    """Read a generated payload.

    :param payload_id: Identifier returned when the payload was created.
    :param service: Payload service.
    :param response: Response, used to attach caching headers.
    :param if_none_match: Validator from a conditional request.
    :return: The payload output, or an empty 304 if the client already has it.
    :raises PayloadNotFoundError: If the payload does not exist (reported as 404).
    """
    output = await service.get_output(payload_id)
    etag = f'"{payload_id}"'
    headers = {"ETag": etag, "Cache-Control": IMMUTABLE_CACHE_CONTROL}
    if _etag_matches(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    response.headers.update(headers)
    return PayloadResponse(output=output)


@router.get("/health")
async def health() -> dict[str, str]:
    """Report that the service is up.

    :return: A static status document.
    """
    return {"status": "ok"}
