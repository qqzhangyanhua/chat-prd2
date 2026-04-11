from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)

    sessions: Mapped[list[ProjectSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan",
    )


class ProjectSession(Base):
    __tablename__ = "project_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    initial_idea: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped[User] = relationship(back_populates="sessions")
    state_versions: Mapped[list[ProjectStateVersion]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
    )
    prd_snapshots: Mapped[list[PrdSnapshot]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
    )
    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
    )


class ProjectStateVersion(Base):
    __tablename__ = "project_state_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("project_sessions.id"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    state_json: Mapped[dict] = mapped_column(JSON)

    session: Mapped[ProjectSession] = relationship(back_populates="state_versions")


class PrdSnapshot(Base):
    __tablename__ = "prd_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("project_sessions.id"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    sections: Mapped[dict] = mapped_column(JSON)

    session: Mapped[ProjectSession] = relationship(back_populates="prd_snapshots")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("project_sessions.id"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String, default="chat")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    session: Mapped[ProjectSession] = relationship(back_populates="messages")


class AssistantReplyGroup(Base):
    __tablename__ = "assistant_reply_groups"
    __table_args__ = (
        UniqueConstraint("id", "session_id", "user_message_id", name="uq_arg_id_session_user_message"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("project_sessions.id"),
        index=True,
    )
    user_message_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_messages.id"),
        unique=True,
    )
    latest_version_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class AssistantReplyVersion(Base):
    __tablename__ = "assistant_reply_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reply_group_id", "session_id", "user_message_id"],
            [
                "assistant_reply_groups.id",
                "assistant_reply_groups.session_id",
                "assistant_reply_groups.user_message_id",
            ],
            name="fk_arv_group_session_user_message",
        ),
        UniqueConstraint("reply_group_id", "version_no", name="uq_arv_group_version_no"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    reply_group_id: Mapped[str] = mapped_column(
        ForeignKey("assistant_reply_groups.id"),
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("project_sessions.id"),
        index=True,
    )
    user_message_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_messages.id"),
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    action_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    model_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    state_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("project_state_versions.id"),
        nullable=True,
    )
    prd_snapshot_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class AgentTurnDecision(Base):
    __tablename__ = "agent_turn_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("project_sessions.id"),
        index=True,
    )
    user_message_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_messages.id"),
        index=True,
        unique=True,
    )
    phase: Mapped[str] = mapped_column(String)
    phase_goal: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    understanding_summary: Mapped[str] = mapped_column(Text)
    assumptions_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    risk_flags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    next_move: Mapped[str] = mapped_column(String)
    suggestions_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    recommendation_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    needs_confirmation_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String)
    state_patch_json: Mapped[dict] = mapped_column(JSON, default=dict)
    prd_patch_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class LLMModelConfig(Base):
    __tablename__ = "llm_model_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    recommended_scene: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recommended_usage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
