from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

# Bounds keep a single request from producing unbounded queries and oversized index keys.
MAX_ITEMS = 1000
MAX_STRING_LENGTH = 1000

Text = Annotated[str, StringConstraints(max_length=MAX_STRING_LENGTH)]
TextList = Annotated[list[Text], Field(min_length=1, max_length=MAX_ITEMS)]


class PayloadRequest(BaseModel):
    list_1: TextList
    list_2: TextList

    @model_validator(mode="after")
    def lists_have_same_length(self) -> Self:
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreated(BaseModel):
    id: str
    message: str


class PayloadResponse(BaseModel):
    output: str
