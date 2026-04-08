"""add recommended usage to llm model configs

Revision ID: 0008_add_recommended_usage_to_llm_model_configs
Revises: 0007_add_agent_turn_decisions
Create Date: 2026-04-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_add_recommended_usage_to_llm_model_configs"
down_revision: Union[str, None] = "0007_add_agent_turn_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_model_configs",
        sa.Column("recommended_usage", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("llm_model_configs", "recommended_usage")
