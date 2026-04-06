from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db.models import User
from app.repositories import assistant_reply_groups as assistant_reply_groups_repository
from app.repositories import assistant_reply_versions as assistant_reply_versions_repository
from app.repositories import messages as messages_repository
from app.repositories import model_configs as model_configs_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
from app.services.messages import apply_prd_patch, apply_state_patch, handle_user_message
from app.services.messages import stream_user_message_events
from app.services.model_gateway import ModelGatewayError


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
        email=f"messages-service-{uuid4()}@example.com",
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


def test_handle_user_message_rolls_back_user_message_when_generate_reply_fails(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="失败模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    def fake_generate_reply(*, base_url, api_key, model, messages):
        raise ModelGatewayError("上游不可用")

    monkeypatch.setattr("app.services.messages.generate_reply", fake_generate_reply)

    with pytest.raises(HTTPException) as exc_info:
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="这轮消息必须回滚",
            model_config_id=model_config.id,
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "上游不可用"
    assert messages_repository.get_messages_for_session(db_session, session.id) == []
    latest_state_version = state_repository.get_latest_state_version(db_session, session.id)
    assert latest_state_version is not None
    assert latest_state_version.version == 1


def test_handle_user_message_logs_model_gateway_context(db_session, monkeypatch, caplog):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="失败模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    def fake_generate_reply(*, base_url, api_key, model, messages):
        raise ModelGatewayError("上游不可用")

    monkeypatch.setattr("app.services.messages.generate_reply", fake_generate_reply)

    with caplog.at_level("WARNING"):
        with pytest.raises(HTTPException):
            handle_user_message(
                db=db_session,
                session_id=session.id,
                session=session,
                content="这轮消息必须记录日志",
                model_config_id=model_config.id,
            )

    assert session.id in caplog.text
    assert model_config.id in caplog.text
    assert "上游不可用" in caplog.text


def test_stream_user_message_events_yields_multiple_deltas_and_persists_reply(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="流式模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    class FakeReplyStream:
        def __iter__(self):
            yield "先把"
            yield "目标用户"
            yield "讲清楚。"

        def close(self):
            return None

    def fake_open_reply_stream(*, base_url, api_key, model, messages):
        assert base_url == "https://gateway.example.com/v1"
        assert api_key == "secret"
        assert model == "gpt-4o-mini"
        assert messages == [
            {"role": "system", "content": "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"},
            {"role": "user", "content": "帮我梳理目标用户"},
        ]
        return FakeReplyStream()

    monkeypatch.setattr("app.services.messages.open_reply_stream", fake_open_reply_stream)

    events = list(
        stream_user_message_events(
            db=db_session,
            session_id=session.id,
            session=session,
            content="帮我梳理目标用户",
            model_config_id=model_config.id,
        )
    )

    assert [event.type for event in events] == [
        "message.accepted",
        "action.decided",
        "assistant.delta",
        "assistant.delta",
        "assistant.delta",
        "assistant.done",
    ]
    assert [event.data["delta"] for event in events if event.type == "assistant.delta"] == [
        "先把",
        "目标用户",
        "讲清楚。",
    ]

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    assert len(persisted_messages) == 2
    assert persisted_messages[1].content == "先把目标用户讲清楚。"


def test_reply_version_writes_do_not_create_new_user_messages(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="版本测试模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: "第一版助手回复",
    )

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请先给我一个初始回复",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")

    reply_group = assistant_reply_groups_repository.create_reply_group(
        db=db_session,
        session_id=session.id,
        user_message_id=user_message.id,
    )
    version_1 = assistant_reply_versions_repository.create_reply_version(
        db=db_session,
        reply_group_id=reply_group.id,
        session_id=session.id,
        user_message_id=user_message.id,
        version_no=1,
        content=assistant_message.content,
        action_snapshot=assistant_message.meta.get("action", {}),
        model_meta={
            "model_config_id": model_config.id,
            "model_name": model_config.model,
            "display_name": model_config.name,
            "base_url": model_config.base_url,
        },
        state_version_id=None,
        prd_snapshot_version=None,
    )
    assistant_reply_groups_repository.set_latest_version(
        db=db_session,
        reply_group=reply_group,
        latest_version_id=version_1.id,
    )

    version_2 = assistant_reply_versions_repository.create_reply_version(
        db=db_session,
        reply_group_id=reply_group.id,
        session_id=session.id,
        user_message_id=user_message.id,
        version_no=2,
        content="第二版助手回复",
        action_snapshot={"action": "probe_deeper"},
        model_meta={"model_config_id": model_config.id},
        state_version_id=None,
        prd_snapshot_version=None,
    )
    assistant_reply_groups_repository.set_latest_version(
        db=db_session,
        reply_group=reply_group,
        latest_version_id=version_2.id,
    )
    db_session.commit()

    refreshed_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    versions = assistant_reply_versions_repository.list_versions_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    persisted_messages_after_version_append = messages_repository.get_messages_for_session(
        db_session,
        session.id,
    )
    user_messages_after_version_append = [
        message for message in persisted_messages_after_version_append if message.role == "user"
    ]

    assert result.user_message_id == user_message.id
    assert refreshed_group is not None
    assert refreshed_group.latest_version_id == version_2.id
    assert [version.version_no for version in versions] == [1, 2]
    assert latest_version is not None
    assert latest_version.id == version_2.id
    assert all(version.user_message_id == user_message.id for version in versions)
    assert all(version.reply_group_id == reply_group.id for version in versions)
    assert len(user_messages_after_version_append) == 1


def test_create_reply_group_rejects_user_message_from_other_session(db_session, monkeypatch):
    primary_session = _create_session_with_state(db_session)
    secondary_session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="group 一致性测试模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: "group 一致性测试回复",
    )

    handle_user_message(
        db=db_session,
        session_id=primary_session.id,
        session=primary_session,
        content="primary",
        model_config_id=model_config.id,
    )
    handle_user_message(
        db=db_session,
        session_id=secondary_session.id,
        session=secondary_session,
        content="secondary",
        model_config_id=model_config.id,
    )

    secondary_messages = messages_repository.get_messages_for_session(db_session, secondary_session.id)
    secondary_user_message = next(message for message in secondary_messages if message.role == "user")

    with pytest.raises(ValueError, match="does not belong to session"):
        assistant_reply_groups_repository.create_reply_group(
            db=db_session,
            session_id=primary_session.id,
            user_message_id=secondary_user_message.id,
        )


def test_create_reply_version_rejects_group_session_or_user_message_mismatch(db_session, monkeypatch):
    primary_session = _create_session_with_state(db_session)
    secondary_session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="一致性测试模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: "一致性测试回复",
    )

    handle_user_message(
        db=db_session,
        session_id=primary_session.id,
        session=primary_session,
        content="primary",
        model_config_id=model_config.id,
    )
    handle_user_message(
        db=db_session,
        session_id=secondary_session.id,
        session=secondary_session,
        content="secondary",
        model_config_id=model_config.id,
    )

    primary_messages = messages_repository.get_messages_for_session(db_session, primary_session.id)
    secondary_messages = messages_repository.get_messages_for_session(db_session, secondary_session.id)
    primary_user_message = next(message for message in primary_messages if message.role == "user")
    secondary_user_message = next(message for message in secondary_messages if message.role == "user")

    primary_group = assistant_reply_groups_repository.create_reply_group(
        db=db_session,
        session_id=primary_session.id,
        user_message_id=primary_user_message.id,
    )
    db_session.commit()

    with pytest.raises(ValueError, match="session_id does not match"):
        assistant_reply_versions_repository.create_reply_version(
            db=db_session,
            reply_group_id=primary_group.id,
            session_id=secondary_session.id,
            user_message_id=primary_user_message.id,
            version_no=1,
            content="不合法版本",
            action_snapshot={},
            model_meta={},
            state_version_id=None,
            prd_snapshot_version=None,
        )

    with pytest.raises(ValueError, match="user_message_id does not match"):
        assistant_reply_versions_repository.create_reply_version(
            db=db_session,
            reply_group_id=primary_group.id,
            session_id=primary_session.id,
            user_message_id=secondary_user_message.id,
            version_no=1,
            content="不合法版本",
            action_snapshot={},
            model_meta={},
            state_version_id=None,
            prd_snapshot_version=None,
        )


def test_get_latest_version_for_group_uses_group_latest_pointer(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="latest 语义模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: "latest 语义测试回复",
    )
    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="latest",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")

    reply_group = assistant_reply_groups_repository.create_reply_group(
        db=db_session,
        session_id=session.id,
        user_message_id=user_message.id,
    )
    version_1 = assistant_reply_versions_repository.create_reply_version(
        db=db_session,
        reply_group_id=reply_group.id,
        session_id=session.id,
        user_message_id=user_message.id,
        version_no=1,
        content=assistant_message.content,
        action_snapshot=assistant_message.meta.get("action", {}),
        model_meta={"model_config_id": model_config.id},
        state_version_id=None,
        prd_snapshot_version=None,
    )
    version_2 = assistant_reply_versions_repository.create_reply_version(
        db=db_session,
        reply_group_id=reply_group.id,
        session_id=session.id,
        user_message_id=user_message.id,
        version_no=2,
        content="候选但非 latest",
        action_snapshot={"action": "probe_deeper"},
        model_meta={"model_config_id": model_config.id},
        state_version_id=None,
        prd_snapshot_version=None,
    )
    assistant_reply_groups_repository.set_latest_version(
        db=db_session,
        reply_group=reply_group,
        latest_version_id=version_1.id,
    )
    db_session.commit()

    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )

    assert latest_version is not None
    assert latest_version.id == version_1.id
    assert latest_version.id != version_2.id
