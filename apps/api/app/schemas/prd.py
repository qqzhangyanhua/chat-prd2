from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PrdSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    version: int
    sections: dict[str, Any] = Field(default_factory=dict)
