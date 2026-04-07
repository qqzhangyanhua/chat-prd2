"""add agent turn decisions table

Revision ID: 0007_add_agent_turn_decisions
Revises: 0006_add_assistant_reply_versions
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_add_agent_turn_decisions"
down_revision: Union[str, None] = "0006_add_assistant_reply_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_turn_decisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("project_sessions.id"), nullable=False),
        sa.Column(
            "user_message_id",
            sa.String(),
            sa.ForeignKey("conversation_messages.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("phase_goal", sa.String(), nullable=True),
        sa.Column("understanding_summary", sa.Text(), nullable=False),
        sa.Column("assumptions_json", sa.JSON(), nullable=False),
        sa.Column("risk_flags_json", sa.JSON(), nullable=False),
        sa.Column("next_move", sa.String(), nullable=False),
        sa.Column("suggestions_json", sa.JSON(), nullable=False),
        sa.Column("recommendation_json", sa.JSON(), nullable=True),
        sa.Column("needs_confirmation_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("state_patch_json", sa.JSON(), nullable=False),
        sa.Column("prd_patch_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_agent_turn_decisions_session_id",
        "agent_turn_decisions",
        ["session_id"],
    )
    op.create_index(
        "ix_agent_turn_decisions_user_message_id",
        "agent_turn_decisions",
        ["user_message_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_turn_decisions_user_message_id", table_name="agent_turn_decisions")
    op.drop_index("ix_agent_turn_decisions_session_id", table_name="agent_turn_decisions")
    op.drop_table("agent_turn_decisions")
