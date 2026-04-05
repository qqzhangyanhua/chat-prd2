"""add created_at to project sessions

Revision ID: 0003_add_project_session_created_at
Revises: 0002_add_project_state_and_prd_snapshot
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_session_created_at"
down_revision: Union[str, None] = "0002_state_prd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_sessions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("project_sessions", "created_at")
