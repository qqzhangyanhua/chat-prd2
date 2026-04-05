"""add project state and prd snapshot tables

Revision ID: 0002_add_project_state_and_prd_snapshot
Revises: 0001_initial
Create Date: 2026-04-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_state_prd"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_state_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("project_sessions.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_project_state_versions_session_id",
        "project_state_versions",
        ["session_id"],
        unique=False,
    )

    op.create_table(
        "prd_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("project_sessions.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_prd_snapshots_session_id",
        "prd_snapshots",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_prd_snapshots_session_id", table_name="prd_snapshots")
    op.drop_table("prd_snapshots")

    op.drop_index(
        "ix_project_state_versions_session_id",
        table_name="project_state_versions",
    )
    op.drop_table("project_state_versions")
