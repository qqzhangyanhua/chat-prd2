from pydantic import BaseModel, Field


class PrdReviewCheckResponse(BaseModel):
    verdict: str
    summary: str
    evidence: list[str] = Field(default_factory=list)


class PrdReviewResponse(BaseModel):
    verdict: str
    status: str
    summary: str
    checks: dict[str, PrdReviewCheckResponse] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    ready_for_confirmation: bool = False
