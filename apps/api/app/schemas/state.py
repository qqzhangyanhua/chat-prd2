from typing import Any

from pydantic import BaseModel


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
