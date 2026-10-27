"""add cached_tokens to ai_call_metrics

Revision ID: z5a6b7c8d9e0
Revises: reportpaths01
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "z5a6b7c8d9e0"
down_revision = "reportpaths01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_call_metrics",
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("ai_call_metrics", "cached_tokens")
