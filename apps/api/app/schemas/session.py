from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.message import AssistantReplyGroupResponse
from app.schemas.message import ConversationMessageResponse
from app.schemas.prd import PrdSnapshotResponse
from app.schemas.state import StateSnapshot


class SessionCreateRequest(BaseModel):
    title: str
    initial_idea: str


NonEmptyTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SessionUpdateRequest(BaseModel):
    title: NonEmptyTitle


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    initial_idea: str
    created_at: object
    updated_at: object


class SessionCreateResponse(BaseModel):
    session: SessionResponse
    state: StateSnapshot
    prd_snapshot: PrdSnapshotResponse
    messages: list[ConversationMessageResponse] = Field(default_factory=list)
    assistant_reply_groups: list[AssistantReplyGroupResponse] = Field(default_factory=list)


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
