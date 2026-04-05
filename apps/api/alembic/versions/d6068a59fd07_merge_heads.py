"""merge_heads and add created_at to conversation_messages

Revision ID: d6068a59fd07
Revises: 0003_add_conversation_messages, 0004_session_updated_at
Create Date: 2026-04-05 21:18:59.644512

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6068a59fd07'
down_revision: Union[str, None] = ('0003_add_conversation_messages', '0004_session_updated_at')
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
