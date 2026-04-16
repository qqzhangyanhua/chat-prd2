from __future__ import annotations

from pydantic import BaseModel, Field


class ReplayTimelineItemResponse(BaseModel):
    id: str
    type: str
    title: str
    summary: str
    event_at: str | None = None
    sections_changed: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

