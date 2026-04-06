"""add assistant reply group and version tables

Revision ID: 0006_add_assistant_reply_versions
Revises: 0005_add_llm_model_configs
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_add_assistant_reply_versions"
down_revision: Union[str, None] = "0005_add_llm_model_configs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_reply_groups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("project_sessions.id"), nullable=False),
        sa.Column(
            "user_message_id",
            sa.String(),
            sa.ForeignKey("conversation_messages.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "latest_version_id",
            sa.String(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "id",
            "session_id",
            "user_message_id",
            name="uq_arg_id_session_user_message",
        ),
    )
    op.create_index(
        "ix_assistant_reply_groups_session_id",
        "assistant_reply_groups",
        ["session_id"],
    )

    op.create_table(
        "assistant_reply_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "reply_group_id",
            sa.String(),
            sa.ForeignKey("assistant_reply_groups.id"),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(), sa.ForeignKey("project_sessions.id"), nullable=False),
        sa.Column(
            "user_message_id",
            sa.String(),
            sa.ForeignKey("conversation_messages.id"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("action_snapshot", sa.JSON(), nullable=False),
        sa.Column("model_meta", sa.JSON(), nullable=False),
        sa.Column(
            "state_version_id",
            sa.String(),
            sa.ForeignKey("project_state_versions.id"),
            nullable=True,
        ),
        sa.Column("prd_snapshot_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["reply_group_id", "session_id", "user_message_id"],
            [
                "assistant_reply_groups.id",
                "assistant_reply_groups.session_id",
                "assistant_reply_groups.user_message_id",
            ],
            name="fk_arv_group_session_user_message",
        ),
        sa.UniqueConstraint(
            "reply_group_id",
            "version_no",
            name="uq_arv_group_version_no",
        ),
    )
    op.create_index(
        "ix_assistant_reply_versions_reply_group_id",
        "assistant_reply_versions",
        ["reply_group_id"],
    )
    op.create_index(
        "ix_assistant_reply_versions_session_id",
        "assistant_reply_versions",
        ["session_id"],
    )
    op.create_index(
        "ix_assistant_reply_versions_user_message_id",
        "assistant_reply_versions",
        ["user_message_id"],
    )
def downgrade() -> None:
    op.drop_index("ix_assistant_reply_versions_user_message_id", table_name="assistant_reply_versions")
    op.drop_index("ix_assistant_reply_versions_session_id", table_name="assistant_reply_versions")
    op.drop_index("ix_assistant_reply_versions_reply_group_id", table_name="assistant_reply_versions")
    op.drop_table("assistant_reply_versions")
    op.drop_index("ix_assistant_reply_groups_session_id", table_name="assistant_reply_groups")
    op.drop_table("assistant_reply_groups")
