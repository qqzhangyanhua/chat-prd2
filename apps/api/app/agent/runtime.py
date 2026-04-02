from __future__ import annotations

from app.agent.prompts import PROBE_TARGET_USER_REPLY, SUMMARIZE_UNDERSTANDING_REPLY
from app.agent.types import AgentResult, NextAction


def decide_next_action(state: dict, user_input: str) -> NextAction:
    del user_input

    if not state.get("target_user"):
        return NextAction(
            action="probe_deeper",
            target="target_user",
            reason="当前还不清楚目标用户是谁，需要继续追问",
        )

    return NextAction(
        action="summarize_understanding",
        target=None,
        reason="已有足够信息，可以先总结当前理解并推动下一步决策",
    )


def run_agent(state: dict, user_input: str) -> AgentResult:
    action = decide_next_action(state, user_input)
    reply = (
        PROBE_TARGET_USER_REPLY
        if action.action == "probe_deeper"
        else SUMMARIZE_UNDERSTANDING_REPLY
    )
    return AgentResult(
        reply=reply,
        action=action,
        state_patch={},
        prd_patch={},
        decision_log=[],
    )
