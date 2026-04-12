from uuid import uuid4

from app.db.models import User
from app.repositories import messages as messages_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
from app.services.message_persistence import persist_assistant_reply_and_version
from app.services.message_preparation import (
    build_gateway_messages_for_regenerate,
    build_model_meta,
)


def _create_session_with_state(db_session):
    user = User(
        id=str(uuid4()),
        email=f"message-pipeline-{uuid4()}@example.com",
        password_hash="hashed",
    )
    db_session.add(user)
    session = sessions_repository.create_session(
        db=db_session,
        user_id=user.id,
        title="消息测试",
        initial_idea="做一个 AI 产品经理",
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=1,
        state_json={"target_user": None, "prd_snapshot": {"sections": {}}},
    )
    db_session.commit()
    return session


def test_build_model_meta_returns_expected_shape():
    model_config = type(
        "ModelConfigStub",
        (),
        {
            "id": "model-1",
            "model": "gpt-4o-mini",
            "name": "通用模型",
            "base_url": "https://gateway.example.com/v1",
        },
    )()

    assert build_model_meta(model_config) == {
        "model_config_id": "model-1",
        "model_name": "gpt-4o-mini",
        "display_name": "通用模型",
        "base_url": "https://gateway.example.com/v1",
    }


def test_build_gateway_messages_for_regenerate_stops_after_target_user_message(db_session):
    session = _create_session_with_state(db_session)
    first_user = messages_repository.create_message(
        db=db_session,
        session_id=session.id,
        role="user",
        content="第一问",
        meta={},
    )
    messages_repository.create_message(
        db=db_session,
        session_id=session.id,
        role="assistant",
        content="第一答",
        meta={},
    )
    second_user = messages_repository.create_message(
        db=db_session,
        session_id=session.id,
        role="user",
        content="第二问",
        meta={},
    )
    messages_repository.create_message(
        db=db_session,
        session_id=session.id,
        role="assistant",
        content="第二答",
        meta={},
    )
    db_session.commit()

    messages = build_gateway_messages_for_regenerate(db_session, session.id, first_user.id)

    assert messages == [
        {"role": "system", "content": "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"},
        {"role": "user", "content": "第一问"},
    ]
    assert second_user.id != first_user.id


def test_persist_assistant_reply_and_version_creates_reply_group_and_assistant_message(
    db_session,
):
    session = _create_session_with_state(db_session)
    user_message = messages_repository.create_message(
        db=db_session,
        session_id=session.id,
        role="user",
        content="帮我梳理目标用户",
        meta={"model_config_id": "model-1"},
    )
    db_session.commit()

    assistant_message_id, reply_group_id, version_no, version_id, prd_snapshot_version, created_at = (
        persist_assistant_reply_and_version(
            db=db_session,
            session_id=session.id,
            session=session,
            user_message_id=user_message.id,
            reply_group_id="group-1",
            assistant_version_id="version-1",
            version_no=1,
            reply="这是整理后的回复",
            model_meta={
                "model_config_id": "model-1",
                "model_name": "gpt-4o-mini",
                "display_name": "通用模型",
                "base_url": "https://gateway.example.com/v1",
            },
            action={"action": "probe_deeper"},
            turn_decision=type(
                "TurnDecisionStub",
                (),
                {
                    "phase": "idea_clarification",
                    "conversation_strategy": "clarify",
                    "strategy_reason": None,
                    "phase_goal": "收敛目标用户",
                    "assumptions": [],
                    "pm_risk_flags": [],
                    "suggestions": [],
                    "recommendation": None,
                    "needs_confirmation": [],
                    "next_best_questions": [],
                    "state_patch": {},
                    "understanding": {"summary": "用户希望梳理目标用户"},
                    "next_move": "probe_for_specificity",
                    "confidence": "medium",
                    "prd_patch": {},
                },
            )(),
            state={"prd_snapshot": {"sections": {}}},
            state_patch={},
            prd_patch={},
            model_config=None,
        )
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")

    assert assistant_message_id == assistant_message.id
    assert reply_group_id == "group-1"
    assert version_no == 1
    assert version_id == "version-1"
    assert prd_snapshot_version == 2
    assert created_at is not None
    assert assistant_message.content == "这是整理后的回复"
