from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.agent.runtime import run_agent
from app.db.models import ProjectSession
from app.repositories import messages as messages_repository
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository


@dataclass(frozen=True, slots=True)
class MessageResult:
    user_message_id: str
    assistant_message_id: str
    action: dict
    reply: str


def apply_state_patch(current_state: dict, patch: dict) -> dict:
    if not patch:
        return current_state
    return {**current_state, **patch}


def apply_prd_patch(current_state: dict, patch: dict) -> dict:
    if not patch:
        return current_state
    sections = current_state.get("prd_snapshot", {}).get("sections", {})
    current_state["prd_snapshot"]["sections"] = {**sections, **patch}
    return current_state


def handle_user_message(
    db: Session,
    session_id: str,
    session: ProjectSession,
    content: str,
) -> MessageResult:
    user_message = messages_repository.create_message(
        db=db,
        session_id=session_id,
        role="user",
        content=content,
    )
    messages_repository.touch_session_activity(db, session)
    db.commit()

    try:
        state = state_repository.get_latest_state(db, session_id)
        agent_result = run_agent(state, content)

        new_state = apply_state_patch(state, agent_result.state_patch)
        new_state = apply_prd_patch(new_state, agent_result.prd_patch)

        latest_version = state_repository.get_latest_state_version(db, session_id)
        next_version = (latest_version.version + 1) if latest_version else 1

        state_repository.create_state_version(db, session_id, next_version, new_state)
        prd_repository.create_prd_snapshot(
            db, session_id, next_version,
            new_state.get("prd_snapshot", {}).get("sections", {}),
        )

        assistant_message = messages_repository.create_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=agent_result.reply,
            meta={"action": asdict(agent_result.action)},
        )
        messages_repository.touch_session_activity(db, session)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return MessageResult(
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        action=asdict(agent_result.action),
        reply=agent_result.reply,
    )
