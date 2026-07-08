"""Initial schema

Revision ID: 001
Create Date: 2026-07-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_profiles",
        sa.Column("user_id", sa.String(32), primary_key=True),
        sa.Column("business_name", sa.String(255), server_default=""),
        sa.Column("industry", sa.String(128), server_default=""),
        sa.Column("revenue_range", sa.String(128), server_default=""),
        sa.Column("team_size", sa.String(64), server_default=""),
        sa.Column("location", sa.String(255), server_default=""),
        sa.Column("pain_points", sa.Text, server_default=""),
        sa.Column("goals", sa.Text, server_default=""),
        sa.Column("phone", sa.String(32), server_default=""),
        sa.Column("raw_data", sa.JSON, server_default="{}"),
        sa.Column("intake_completed", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer, autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, server_default="0"),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("cost", sa.Float, server_default="0.0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index("ix_token_usage_user_id", "token_usage", ["user_id"])


def downgrade() -> None:
    op.drop_table("token_usage")
    op.drop_table("business_profiles")
