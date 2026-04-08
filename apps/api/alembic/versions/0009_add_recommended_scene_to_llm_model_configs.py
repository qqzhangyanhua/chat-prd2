"""add recommended scene to llm model configs

Revision ID: 0009_add_recommended_scene_to_llm_model_configs
Revises: 0008_add_recommended_usage_to_llm_model_configs
Create Date: 2026-04-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_add_recommended_scene_to_llm_model_configs"
down_revision: Union[str, None] = "0008_add_recommended_usage_to_llm_model_configs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_model_configs",
        sa.Column("recommended_scene", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("llm_model_configs", "recommended_scene")
