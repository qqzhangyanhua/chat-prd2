from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

GUIDANCE_SUGGESTION_COUNT = 4

ActionName = Literal["probe_deeper", "summarize_understanding"]
ActionTarget = Literal["target_user", "problem", "solution", "mvp_scope"]
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


@dataclass
class PmMentorOutput:
    observation: str
    challenge: str
    suggestion: str
    question: str
    reply: str
    prd_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    confidence: Literal["high", "medium", "low"] = "medium"
    next_focus: str = "problem"
    suggestions: list[Suggestion] = field(default_factory=list)
    recommendation: dict[str, Any] | None = None
    next_move: NextMove | None = None
