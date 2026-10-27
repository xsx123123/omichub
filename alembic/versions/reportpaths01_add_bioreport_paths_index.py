"""Persist BioReport project metadata and report.paths.json artifact index."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "reportpaths01"
down_revision: str | None = "welcome_pool01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("report_schema_version", sa.String(16), nullable=True))
    op.add_column("reports", sa.Column("report_paths_json_path", sa.String(1024), nullable=True))
    op.add_column("reports", sa.Column("project_id", sa.String(120), nullable=True))
    op.add_column("reports", sa.Column("project_user_id", sa.Uuid(), nullable=True))
    op.add_column("reports", sa.Column("project_client", sa.String(200), nullable=True))
    op.add_column("reports", sa.Column("project_species", sa.String(120), nullable=True))
    op.add_column("reports", sa.Column("genome_version", sa.String(120), nullable=True))
    op.add_column("reports", sa.Column("pipeline_version", sa.String(80), nullable=True))
    op.add_column("reports", sa.Column("analysis_date", sa.String(32), nullable=True))
    op.add_column(
        "reports",
        sa.Column("stats", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "reports",
        sa.Column("enrichment_summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "reports",
        sa.Column("files_index", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("reports", sa.Column("metadata_error", sa.Text(), nullable=True))
    op.create_index("ix_reports_project_id", "reports", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_reports_project_id", table_name="reports")
    for name in (
        "metadata_error",
        "files_index",
        "enrichment_summary",
        "stats",
        "analysis_date",
        "pipeline_version",
        "genome_version",
        "project_species",
        "project_user_id",
        "project_client",
        "project_id",
        "report_paths_json_path",
        "report_schema_version",
    ):
        op.drop_column("reports", name)
