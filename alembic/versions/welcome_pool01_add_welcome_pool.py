"""Offline welcome pools, agent audit and daily delivery reservations."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "welcome_pool01"
down_revision = "project_lifecycle01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "welcome_batches",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("audience", sa.String(24), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("prompt_sha256", sa.String(64), nullable=False),
        sa.Column("validation_report", pg.JSONB(), nullable=False),
        sa.Column("reviewed_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("review_note", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "week_start", "audience", "locale", "revision", name="uq_welcome_batch_revision"
        ),
        sa.CheckConstraint("audience IN ('admin','general')", name="ck_welcome_audience"),
        sa.CheckConstraint(
            "status IN ('generating','validated','scheduled','active','retired','failed','withdrawn')",
            name="ck_welcome_batch_status",
        ),
    )
    op.create_index(
        "uq_welcome_one_active",
        "welcome_batches",
        ["audience", "locale"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "welcome_generation_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("welcome_batches.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("lease_token", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("calls", pg.JSONB(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "welcome_messages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("welcome_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("topic", sa.String(32), nullable=False),
        sa.Column("tone", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("disabled_reason", sa.Text()),
        sa.Column(
            "agent_run_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("welcome_generation_runs.id"),
            nullable=False,
        ),
        sa.UniqueConstraint("batch_id", "text_sha256", name="uq_welcome_message_hash"),
    )
    op.create_index("ix_welcome_messages_enabled", "welcome_messages", ["batch_id", "enabled"])
    op.create_table(
        "welcome_deliveries",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("batch_id", pg.UUID(as_uuid=True), sa.ForeignKey("welcome_batches.id")),
        sa.Column("message_id", pg.UUID(as_uuid=True), sa.ForeignKey("welcome_messages.id")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("shown_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "local_date", name="uq_welcome_user_date"),
        sa.CheckConstraint("status IN ('reserved','shown')", name="ck_welcome_delivery_status"),
    )
    op.create_index("ix_welcome_deliveries_recent", "welcome_deliveries", ["user_id", "shown_at"])


def downgrade() -> None:
    # Deployment rollback normally disables the flag and keeps audit. Explicit schema
    # downgrade is destructive; export the four tables before invoking it.
    op.drop_table("welcome_deliveries")
    op.drop_table("welcome_messages")
    op.drop_table("welcome_generation_runs")
    op.drop_table("welcome_batches")
