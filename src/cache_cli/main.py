"""Command line client for exercising the cache service."""

import json
import sys
from collections.abc import Sequence
from contextlib import nullcontext
from typing import TextIO

import httpx
from pydantic import ValidationError
from pydantic_settings import CliApp

from cache_cli.settings import STDIO, CliSettings
from cache_service.api.schemas import PayloadRequest
from cache_service.domain.payload import InvalidPayloadError
from cache_service.services.payload import PayloadService

REQUEST_TIMEOUT_SECONDS = 10


def load_request(settings: CliSettings) -> PayloadRequest:
    """Read and validate the request body from the configured source.

    :param settings: Parsed command line options.
    :return: The validated request body.
    :raises pydantic.ValidationError: If the body is malformed.
    :raises InvalidPayloadError: If the lists cannot be combined.
    :raises OSError: If the input file cannot be read.
    """
    if settings.json_data is not None:
        raw = settings.json_data
    elif settings.input == STDIO:
        raw = sys.stdin.read()
    else:
        assert settings.input is not None  # guaranteed by CliSettings validation
        raw = settings.input.read_text()
    request = PayloadRequest.model_validate_json(raw)
    PayloadService.validate_lists(request.list_1, request.list_2)
    return request


def run(settings: CliSettings, client: httpx.Client, out: TextIO) -> None:
    """Create the payload ``repeat`` times and read it back, one JSON line per iteration.

    Repeating the same request shows the cache at work: every iteration after the first
    should return the same id.

    :param settings: Parsed command line options.
    :param client: HTTP client pointed at the service.
    :param out: Stream receiving one ``{"id", "output"}`` JSON line per iteration.
    :raises httpx.HTTPError: If a request fails or the service answers with an error status.
    """
    body = load_request(settings).model_dump()
    for _ in range(settings.repeat):
        created = client.post("/payload", json=body)
        created.raise_for_status()
        id_ = created.json()["id"]
        payload = client.get(f"/payload/{id_}")
        payload.raise_for_status()
        out.write(json.dumps({"id": id_, "output": payload.json()["output"]}) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line tool.

    :param argv: Command line arguments; ``sys.argv`` is used when omitted.
    :return: Process exit code: 0 on success, 1 on any reported error.
    """
    try:
        settings = CliApp.run(CliSettings, cli_args=list(argv) if argv is not None else None)
        output = nullcontext(sys.stdout) if settings.output == STDIO else settings.output.open("w")
        with (
            httpx.Client(base_url=str(settings.host), timeout=REQUEST_TIMEOUT_SECONDS) as client,
            output as out,
        ):
            run(settings, client, out)
    except (httpx.HTTPError, ValidationError, InvalidPayloadError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
