from typing import Any

from pydantic import BaseModel, Field


class StateSnapshot(BaseModel):
    idea: str
    stage_hint: str
    iteration: int
    goal: str | None
    target_user: str | None
    problem: str | None
    solution: str | None
    mvp_scope: list[str]
    success_metrics: list[str]
    known_facts: dict[str, Any]
    assumptions: list[str]
    risks: list[str]
    unexplored_areas: list[str]
    options: list[str]
    decisions: list[str]
    open_questions: list[str]
    prd_snapshot: dict[str, Any]
    current_phase: str = Field(default="idea_clarification")
    conversation_strategy: str = Field(default="clarify")
    current_model_scene: str = Field(default="general")
    collaboration_mode_label: str | None = None
    strategy_reason: str | None = None
    phase_goal: str | None = None
    working_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    decision_readiness: str | None = None
    pm_risk_flags: list[str] = Field(default_factory=list)
    recommended_directions: list[dict[str, Any]] = Field(default_factory=list)
    pending_confirmations: list[str] = Field(default_factory=list)
    rejected_options: list[str] = Field(default_factory=list)
    next_best_questions: list[str] = Field(default_factory=list)
