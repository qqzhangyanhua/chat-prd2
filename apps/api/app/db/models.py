from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
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
