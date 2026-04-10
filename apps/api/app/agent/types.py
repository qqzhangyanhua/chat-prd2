from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ActionName = Literal["probe_deeper", "summarize_understanding"]
ActionTarget = Literal["target_user", "problem", "solution", "mvp_scope"]
NextMove = Literal[
    "probe_for_specificity",
    "assume_and_advance",
    "challenge_and_reframe",
    "summarize_and_confirm",
    "force_rank_or_choose",
]
ConversationStrategy = Literal["clarify", "converge", "confirm", "choose"]
SuggestionType = Literal["direction", "tradeoff", "recommendation", "warning"]

UnderstandingRiskHint = Literal["user_too_broad", "problem_too_vague", "solution_before_problem"]


WorkflowStage = Literal[
    "idea_parser",
    "prd_draft",
    "critic_review",
    "refine_loop",
    "finalize",
    "completed",
]


@dataclass(frozen=True, slots=True)
class NextAction:
    action: ActionName
    target: ActionTarget | None
    reason: str


@dataclass(slots=True)
class AgentResult:
    reply: str
    action: NextAction
    reply_mode: Literal["gateway", "local"] = "gateway"
    state_patch: dict[str, Any] = field(default_factory=dict)
    prd_patch: dict[str, Any] = field(default_factory=dict)
    decision_log: list[dict[str, Any]] = field(default_factory=list)
    understanding: "UnderstandingResult | None" = None
    turn_decision: "TurnDecision | None" = None


@dataclass(slots=True)
class Suggestion:
    type: SuggestionType
    label: str
    content: str
    rationale: str
    priority: int


@dataclass(slots=True)
class UnderstandingResult:
    summary: str
    candidate_updates: dict[str, Any]
    assumption_candidates: list[str]
    ambiguous_points: list[str]
    risk_hints: list[UnderstandingRiskHint]


@dataclass(slots=True)
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


@dataclass(slots=True)
class IdeaParseResult:
    idea_summary: str
    product_type: str | None = None
    domain_signals: list[str] = field(default_factory=list)
    explicit_requirements: list[str] = field(default_factory=list)
    implicit_assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


@dataclass(slots=True)
class PrdDraftResult:
    version: int = 1
    status: Literal["draft_hypothesis", "draft_refined", "ready_for_finalize"] = "draft_hypothesis"
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    critic_ready: bool = False


@dataclass(slots=True)
class CriticResult:
    overall_verdict: Literal["pass", "revise", "block"]
    strengths: list[str] = field(default_factory=list)
    major_gaps: list[str] = field(default_factory=list)
    minor_gaps: list[str] = field(default_factory=list)
    question_queue: list[str] = field(default_factory=list)
    blocking_questions: list[str] = field(default_factory=list)
    recommended_next_focus: str | None = None
    revision_instructions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PmMentorOutput:
    observation: str
    challenge: str
    suggestion: str
    question: str
    reply: str
    prd_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    confidence: Literal["high", "medium", "low"] = "medium"
    next_focus: str = "problem"
