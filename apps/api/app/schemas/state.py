from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agent.types import (
    AssertionState,
    ConversationStrategy,
    DraftCompleteness,
    EvidenceKind,
    WorkflowStage,
)


class DraftEntryPayload(BaseModel):
    id: str
    text: str
    assertion_state: AssertionState
    evidence_ref_ids: list[str] = Field(default_factory=list)
    derived_from_diagnostics: list[str] = Field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class DraftSectionPayload(BaseModel):
    title: str
    entries: list[DraftEntryPayload] = Field(default_factory=list)
    completeness: DraftCompleteness = Field(default="missing")
    summary: str | None = None
    content: str | None = None
    status: str | None = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class EvidenceItemPayload(BaseModel):
    id: str
    kind: EvidenceKind
    excerpt: str
    section_keys: list[str] = Field(default_factory=list)
    message_id: str | None = None
    turn_decision_id: str | None = None
    created_at: str | None = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class PrdDraftPayload(BaseModel):
    version: int = 1
    status: str = "drafting"
    sections: dict[str, DraftSectionPayload] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class StateSnapshot(BaseModel):
    model_config = {"extra": "ignore"}

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
    conversation_strategy: ConversationStrategy = Field(default="clarify")
    current_model_scene: str = Field(default="general")
    collaboration_mode_label: str | None = None
    strategy_reason: str | None = None
    phase_goal: str | None = None
    working_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[EvidenceItemPayload] = Field(default_factory=list)
    decision_readiness: str | None = None
    pm_risk_flags: list[str] = Field(default_factory=list)
    recommended_directions: list[dict[str, Any]] = Field(default_factory=list)
    pending_confirmations: list[str] = Field(default_factory=list)
    rejected_options: list[str] = Field(default_factory=list)
    next_best_questions: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    diagnostic_summary: dict[str, int] = Field(default_factory=dict)
    response_mode: str = Field(default="direct_answer")
    guidance_mode: str = Field(default="explore")
    guidance_step: str = Field(default="answer")
    focus_dimension: str | None = None
    transition_reason: str | None = None
    transition_trigger: str | None = None
    option_cards: list[dict[str, Any]] = Field(default_factory=list)
    freeform_affordance: dict[str, Any] | None = None
    available_mode_switches: list[dict[str, Any]] = Field(default_factory=list)
    workflow_stage: WorkflowStage | None = Field(default="idea_parser")
    idea_parse_result: dict[str, Any] | None = None
    prd_draft: PrdDraftPayload | None = None
    critic_result: dict[str, Any] | None = None
    refine_history: list[dict[str, Any]] = Field(default_factory=list)
    finalization_ready: bool | None = False
    finalize_confirmation_source: str | None = None
    finalize_preference: str | None = None
    legacy_backfill_version: str | None = None

    @field_validator("workflow_stage", mode="before")
    @classmethod
    def _normalize_legacy_workflow_stage(cls, value: object) -> object:
        _legacy: dict[str, str] = {
            "prd_draft": "refine_loop",
            "critic_review": "refine_loop",
        }
        if isinstance(value, str):
            return _legacy.get(value, value)
        return value
