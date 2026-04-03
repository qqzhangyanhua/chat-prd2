from pydantic import BaseModel, ConfigDict

from app.schemas.prd import PrdSnapshotResponse
from app.schemas.state import StateSnapshot


class SessionCreateRequest(BaseModel):
    title: str
    initial_idea: str


class SessionUpdateRequest(BaseModel):
    title: str


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


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
