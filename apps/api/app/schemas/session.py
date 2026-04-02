from pydantic import BaseModel, ConfigDict

from app.schemas.prd import PrdSnapshotResponse
from app.schemas.state import StateSnapshot


class SessionCreateRequest(BaseModel):
    title: str
    initial_idea: str


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    initial_idea: str


class SessionCreateResponse(BaseModel):
    session: SessionResponse
    state: StateSnapshot
    prd_snapshot: PrdSnapshotResponse
