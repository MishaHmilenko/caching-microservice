from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Bounds keep a single request from producing unbounded queries and oversized index keys.
MAX_ITEMS = 1000
MAX_STRING_LENGTH = 1000

Text = Annotated[str, StringConstraints(max_length=MAX_STRING_LENGTH)]
TextList = Annotated[list[Text], Field(min_length=1, max_length=MAX_ITEMS)]


class PayloadRequest(BaseModel):
    list_1: TextList
    list_2: TextList


class PayloadCreated(BaseModel):
    id: str
    message: str


class PayloadResponse(BaseModel):
    output: str
