from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ActionName = Literal["probe_deeper", "summarize_understanding"]
ActionTarget = Literal["target_user"]


@dataclass(frozen=True, slots=True)
class NextAction:
    action: ActionName
    target: ActionTarget | None
    reason: str


@dataclass(slots=True)
class AgentResult:
    reply: str
    action: NextAction
    state_patch: dict[str, Any] = field(default_factory=dict)
    prd_patch: dict[str, Any] = field(default_factory=dict)
    decision_log: list[dict[str, Any]] = field(default_factory=list)
