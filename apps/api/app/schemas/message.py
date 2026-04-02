from pydantic import BaseModel, Field


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)
