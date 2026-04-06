from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db.models import User
from app.repositories import messages as messages_repository
from app.repositories import model_configs as model_configs_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
from app.services.messages import apply_prd_patch, apply_state_patch, handle_user_message


def test_apply_state_patch_empty_patch_returns_original():
    state = {"idea": "test", "target_user": None}
    result = apply_state_patch(state, {})
    assert result is state


def test_apply_state_patch_merges_keys():
    state = {"idea": "test", "target_user": None, "problem": None}
    result = apply_state_patch(state, {"target_user": "developers", "problem": "too slow"})
    assert result["target_user"] == "developers"
    assert result["problem"] == "too slow"
    assert result["idea"] == "test"


def test_apply_prd_patch_empty_patch_returns_original():
    state = {"prd_snapshot": {"sections": {}}}
    result = apply_prd_patch(state, {})
    assert result is state


def test_apply_prd_patch_merges_sections():
    state = {
        "prd_snapshot": {
            "sections": {"target_user": {"content": "old"}}
        }
    }
    result = apply_prd_patch(state, {"problem": {"content": "new problem"}})
    assert result["prd_snapshot"]["sections"]["target_user"]["content"] == "old"
    assert result["prd_snapshot"]["sections"]["problem"]["content"] == "new problem"


def test_apply_prd_patch_overwrites_existing_section():
    state = {
        "prd_snapshot": {
            "sections": {"target_user": {"content": "old"}}
        }
    }
    result = apply_prd_patch(state, {"target_user": {"content": "updated"}})
    assert result["prd_snapshot"]["sections"]["target_user"]["content"] == "updated"


def _create_session_with_state(db_session):
    user = User(
        id=str(uuid4()),
        email="messages-service@example.com",
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


def test_handle_user_message_rejects_missing_model_config(db_session):
    session = _create_session_with_state(db_session)

    with pytest.raises(HTTPException) as exc_info:
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="帮我分析用户画像",
            model_config_id="missing-config",
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Model config not found"


def test_handle_user_message_rejects_disabled_model_config(db_session):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="禁用模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=False,
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="帮我分析用户画像",
            model_config_id=model_config.id,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Model config is disabled"


def test_handle_user_message_uses_selected_model_and_persists_model_metadata(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="OpenAI 兼容模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    captured = {}

    def fake_generate_reply(*, base_url, api_key, model, messages):
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        captured["model"] = model
        captured["messages"] = messages
        return "这是网关生成的回复"

    monkeypatch.setattr("app.services.messages.generate_reply", fake_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="帮我梳理目标用户",
        model_config_id=model_config.id,
    )

    assert result.reply == "这是网关生成的回复"
    assert captured == {
        "base_url": "https://gateway.example.com/v1",
        "api_key": "secret",
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"},
            {"role": "user", "content": "帮我梳理目标用户"},
        ],
    }

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    assert len(persisted_messages) == 2

    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")

    expected_model_meta = {
        "model_config_id": model_config.id,
        "model_name": "gpt-4o-mini",
        "display_name": "OpenAI 兼容模型",
        "base_url": "https://gateway.example.com/v1",
    }
    assert user_message.meta == expected_model_meta
    assert assistant_message.meta["action"]["action"] == "probe_deeper"
    assert assistant_message.meta["model_config_id"] == model_config.id
    assert assistant_message.meta["model_name"] == "gpt-4o-mini"
    assert assistant_message.meta["display_name"] == "OpenAI 兼容模型"
    assert assistant_message.meta["base_url"] == "https://gateway.example.com/v1"
