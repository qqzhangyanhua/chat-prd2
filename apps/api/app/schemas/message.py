from pydantic import BaseModel, ConfigDict, Field


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    message_type: str
