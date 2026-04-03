"""add created_at to conversation messages

Revision ID: 0005_add_message_created_at
Revises: 0004_add_project_session_updated_at
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_add_message_created_at"
down_revision: Union[str, None] = "0004_add_project_session_updated_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("conversation_messages", "created_at")
