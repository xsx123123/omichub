"""Allow explicitly identified external deliveries without inventing execution Tasks."""

import sqlalchemy as sa
from alembic import op

revision = "flowreportimport01"
down_revision = "z5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("external_source_key", sa.String(1024), nullable=True))
    op.add_column("reports", sa.Column("external_source_digest", sa.String(64), nullable=True))
    op.alter_column("reports", "task_id", existing_type=sa.Uuid(), nullable=True)
    op.create_check_constraint(
        "ck_reports_execution_source",
        "reports",
        "task_id IS NOT NULL OR (external_source_key IS NOT NULL AND external_source_digest IS NOT NULL AND report_kind = 'scientific')",
    )
    op.create_index(
        "uq_reports_external_source",
        "reports",
        ["user_id", "external_source_key", "external_source_digest"],
        unique=True,
    )


def downgrade() -> None:
    # Deliberately fail rather than discard external reports or fabricate task IDs.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM reports WHERE task_id IS NULL")):
        raise RuntimeError("Archive external reports before reverting this migration")
    op.drop_index("uq_reports_external_source", table_name="reports")
    op.drop_constraint("ck_reports_execution_source", "reports", type_="check")
    op.alter_column("reports", "task_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("reports", "external_source_digest")
    op.drop_column("reports", "external_source_key")
