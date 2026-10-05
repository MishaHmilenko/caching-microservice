"""Command line options of cache-cli."""

from pathlib import Path
from typing import Self

from pydantic import AliasChoices, AnyHttpUrl, Field, PositiveInt, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cache_service.api.schemas import PayloadRequest
from cache_service.services.payload import PayloadService

STDIO = Path("-")


class CliSettings(BaseSettings):
    """Command line options for cache-cli."""

    # Pydantic validates everything up front, so bad input fails before any request is sent.
    # ``-h`` is reserved for ``--help`` (argparse), so the host flag is ``-H``.
    # Case-sensitive, otherwise ``-H`` would collapse into ``-h``.
    model_config = SettingsConfigDict(case_sensitive=True, cli_kebab_case=True)

    host: AnyHttpUrl = Field(
        AnyHttpUrl("http://localhost:8000"),
        validation_alias=AliasChoices("H", "host"),
        description="Base URL of the cache service",
    )
    repeat: PositiveInt = Field(
        1,
        validation_alias=AliasChoices("r", "repeat"),
        description="Number of times to send the request",
    )
    input: Path | None = Field(
        None,
        validation_alias=AliasChoices("i", "input"),
        description="JSON file with the request body, or '-' for stdin",
    )
    # Named ``json_data`` because ``json`` would shadow a BaseModel attribute.
    json_data: str | None = Field(
        None,
        validation_alias=AliasChoices("j", "json"),
        description="Request body as a JSON string",
    )
    output: Path = Field(
        STDIO,
        validation_alias=AliasChoices("o", "output"),
        description="File to write results to, or '-' for stdout",
    )

    @field_validator("input")
    @classmethod
    def input_file_exists(cls, value: Path | None) -> Path | None:
        """Ensure that an input file, if given, exists.

        :param value: The ``--input`` value.
        :return: The unchanged value.
        :raises ValueError: If a file path was given and the file does not exist.
        """
        if value is not None and value != STDIO and not value.is_file():
            raise ValueError(f"input file not found: {value}")
        return value

    @field_validator("json_data")
    @classmethod
    def json_is_valid_request(cls, value: str | None) -> str | None:
        """Ensure that inline JSON, if given, is a valid request body.

        :param value: The ``--json`` value.
        :return: The unchanged value.
        :raises ValueError: If the JSON is malformed or the lists cannot be combined.
        """
        if value is not None:
            request = PayloadRequest.model_validate_json(value)
            PayloadService.validate_lists(request.list_1, request.list_2)
        return value

    @model_validator(mode="after")
    def exactly_one_input_source(self) -> Self:
        """Ensure that exactly one of ``--input`` and ``--json`` was given.

        :return: The validated settings.
        :raises ValueError: If both or neither were given.
        """
        if (self.input is None) == (self.json_data is None):
            raise ValueError("provide exactly one of --input or --json")
        return self
