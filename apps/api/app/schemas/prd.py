from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PrdSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    version: int
    sections: dict[str, Any] = Field(default_factory=dict)
    meta: dict | None = None
    sections_changed: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    gap_prompts: list[str] = Field(default_factory=list)
    ready_for_confirmation: bool = False
