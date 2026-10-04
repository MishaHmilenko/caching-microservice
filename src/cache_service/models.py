from sqlmodel import Field, SQLModel


class TransformedString(SQLModel, table=True):
    """Cached outcome of the transformer for a single input string.

    Caching per string (rather than per request) lets unrelated payloads share work.
    """

    source: str = Field(primary_key=True)
    result: str


class Payload(SQLModel, table=True):
    """A generated payload, keyed by a digest of the inputs that produced it."""

    id: str = Field(primary_key=True)
    output: str
