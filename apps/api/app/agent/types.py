from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

GUIDANCE_SUGGESTION_COUNT = 4

ActionName = Literal["probe_deeper", "summarize_understanding", "finalize"]
ActionTarget = Literal["target_user", "problem", "solution", "mvp_scope"]
ResponseMode = Literal["options_first", "direct_answer", "confirm_reply"]
GuidanceMode = Literal["explore", "narrow", "compare", "confirm"]
GuidanceStep = Literal["answer", "choose", "compare", "confirm", "freeform"]
FocusDimension = Literal["target_user", "problem", "solution", "boundary", "constraint", "validation"]
DiagnosticType = Literal["contradiction", "gap", "assumption"]
DiagnosticBucket = Literal["unknown", "risk", "to_validate"]
DiagnosticStatus = Literal["open", "resolved", "superseded"]
DiagnosticConfidence = Literal["high", "medium", "low"]
AssertionState = Literal["confirmed", "inferred", "to_validate"]
DraftCompleteness = Literal["complete", "partial", "missing"]
EvidenceKind = Literal["user_message", "assistant_decision", "system_inference", "diagnostic"]
NextMove = Literal[
    "probe_for_specificity",
    "assume_and_advance",
    "challenge_and_reframe",
    "summarize_and_confirm",
    "force_rank_or_choose",
]
ConversationStrategy = Literal["greet", "clarify", "converge", "confirm", "choose"]
SuggestionType = Literal["direction", "tradeoff", "recommendation", "warning"]

UnderstandingRiskHint = Literal["user_too_broad", "problem_too_vague", "solution_before_problem"]


WorkflowStage = Literal["idea_parser", "refine_loop", "finalize", "completed"]


class SuggestedNextStep(TypedDict):
    action_kind: str
    label: str
    prompt: str


class DiagnosticItem(TypedDict):
    id: str
    type: DiagnosticType
    bucket: DiagnosticBucket
    status: DiagnosticStatus
    title: str
    detail: str
    impact_scope: list[str]
    suggested_next_step: SuggestedNextStep
    confidence: DiagnosticConfidence


class DiagnosticSummary(TypedDict):
    open_count: int
    unknown_count: int
    risk_count: int
    to_validate_count: int


@dataclass(frozen=True)
class DraftEntry:
    id: str
    text: str
    assertion_state: AssertionState
    evidence_ref_ids: list[str] = field(default_factory=list)
    derived_from_diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DraftSection:
    title: str
    entries: list[DraftEntry] = field(default_factory=list)
    completeness: DraftCompleteness = "missing"
    summary: str | None = None


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    kind: EvidenceKind
    excerpt: str
    section_keys: list[str] = field(default_factory=list)
    message_id: str | None = None
    turn_decision_id: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class DraftUpdateSummary:
    section_keys: list[str] = field(default_factory=list)
    entry_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NextAction:
    action: ActionName
    target: ActionTarget | None
    reason: str
    observation: str = ""
    challenge: str = ""
    suggestion: str = ""
    question: str = ""


@dataclass
class AgentResult:
    reply: str
    action: NextAction
    reply_mode: Literal["gateway", "local"] = "gateway"
    state_patch: dict[str, Any] = field(default_factory=dict)
    prd_patch: dict[str, Any] = field(default_factory=dict)
    decision_log: list[dict[str, Any]] = field(default_factory=list)
    understanding: "UnderstandingResult | None" = None
    turn_decision: "TurnDecision | None" = None


@dataclass
class Suggestion:
    type: SuggestionType
    label: str
    content: str
    rationale: str
    priority: int


@dataclass
class UnderstandingResult:
    summary: str
    candidate_updates: dict[str, Any]
    assumption_candidates: list[str]
    ambiguous_points: list[str]
    risk_hints: list[UnderstandingRiskHint]


@dataclass
class TurnDecision:
    phase: str
    phase_goal: str | None
    understanding: dict[str, Any]
    assumptions: list[dict[str, Any]]
    gaps: list[str]
    challenges: list[str]
    pm_risk_flags: list[str]
    next_move: NextMove
    suggestions: list[Suggestion]
    recommendation: dict[str, Any] | None
    reply_brief: dict[str, Any]
    state_patch: dict[str, Any]
    prd_patch: dict[str, Any]
    needs_confirmation: list[str]
    confidence: Literal["high", "medium", "low"]
    strategy_reason: str | None = None
    next_best_questions: list[str] = field(default_factory=list)
    conversation_strategy: ConversationStrategy = "clarify"
    phase_subfocus: str | None = None
    response_mode: ResponseMode = "direct_answer"
    guidance_mode: GuidanceMode = "explore"
    guidance_step: GuidanceStep = "answer"
    focus_dimension: FocusDimension | None = None
    transition_reason: str | None = None
    transition_trigger: str | None = None
    option_cards: list[dict[str, Any]] = field(default_factory=list)
    freeform_affordance: dict[str, Any] | None = None
    can_switch_mode: bool = False
    available_mode_switches: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[DiagnosticItem] = field(default_factory=list)
    diagnostic_summary: DiagnosticSummary = field(
        default_factory=lambda: {
            "open_count": 0,
            "unknown_count": 0,
            "risk_count": 0,
            "to_validate_count": 0,
        }
    )
    draft_summary: DraftUpdateSummary | None = None


@dataclass
class PmMentorOutput:
    observation: str
    challenge: str
    suggestion: str
    question: str
    reply: str
    phase_subfocus: str | None = None
    prd_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    confidence: Literal["high", "medium", "low"] = "medium"
    next_focus: str = "problem"
    raw_suggestion_count: int = 0
    suggestions: list[Suggestion] = field(default_factory=list)
    recommendation: dict[str, Any] | None = None
    next_move: NextMove | None = None
