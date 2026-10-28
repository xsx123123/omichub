"""报告中心 ORM 模型"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cygnusx.infrastructure.database.base import Base, TimestampMixin


class ReportModel(Base, TimestampMixin):
    """分析报告表"""

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_created_at", "created_at"),
        Index("uq_reports_external_source", "user_id", "external_source_key", "external_source_digest", unique=True),
        CheckConstraint(
            "task_id IS NOT NULL OR (external_source_key IS NOT NULL AND external_source_digest IS NOT NULL AND report_kind = 'scientific')",
            name="ck_reports_execution_source",
        ),
        Index(
            "uq_reports_snapshot_template",
            "user_id",
            "snapshot_id",
            "template_version",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    external_source_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    external_source_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    flow_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    flow_name: Mapped[str] = mapped_column(String(100), default="")
    flow_version: Mapped[str] = mapped_column(String(20), default="")
    flow_icon: Mapped[str] = mapped_column(String(50), default="")

    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="generating", index=True)

    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[int] = mapped_column(Integer, default=0)  # 秒

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)

    # 版本树（OmicStudio 产物回填）：parent_id 指向被优化的原报告，version 为父版本+1
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, server_default="1")

    result_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("result_manifest_observations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    report_kind: Mapped[str] = mapped_column(
        String(32), default="scientific", server_default="scientific", nullable=False
    )
    # BioReport paths.json is the metadata and artifact index for native reports.
    # user_id above is also the required owner binding represented by project.user_id.
    report_schema_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    report_paths_json_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    project_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    project_client: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project_species: Mapped[str | None] = mapped_column(String(120), nullable=True)
    genome_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pipeline_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    analysis_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    enrichment_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    files_index: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metadata_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_snapshots.id", ondelete="RESTRICT"), nullable=True
    )
    template_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence_partial: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    files: Mapped[list["ReportFileModel"]] = relationship(
        "ReportFileModel", back_populates="report", cascade="all, delete-orphan"
    )


class ReportFileModel(Base, TimestampMixin):
    """报告文件表"""

    __tablename__ = "report_files"
    __table_args__ = (
        CheckConstraint(
            "(report_id IS NOT NULL AND project_report_job_id IS NULL) OR (report_id IS NULL AND project_report_job_id IS NOT NULL)",
            name="ck_report_files_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), index=True, nullable=True
    )
    project_report_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_report_jobs.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # html/pdf/png/zip/csv
    size: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[str] = mapped_column(String(500), default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    file_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("file_records.id", ondelete="RESTRICT"), nullable=True
    )
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    report: Mapped["ReportModel | None"] = relationship("ReportModel", back_populates="files")


class ReportSnapshotModel(Base, TimestampMixin):
    """Immutable owner-scoped evidence captured before rendering."""

    __tablename__ = "report_snapshots"
    __table_args__ = (
        Index("uq_report_snapshots_digest", "user_id", "task_id", "snapshot_digest", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportGenerationJobModel(Base, TimestampMixin):
    """Durable state machine for reproducible report generation."""

    __tablename__ = "report_generation_jobs"
    __table_args__ = (
        Index("ix_report_generation_jobs_user_id_created_at", "user_id", "created_at"),
        Index("uq_report_generation_jobs_idempotency_key", "idempotency_key", unique=True),
        Index(
            "uq_report_generation_jobs_active",
            "user_id",
            "task_id",
            "template_version",
            unique=True,
            postgresql_where=text("status IN ('queued','collecting','rendering','publishing')"),
            sqlite_where=text("status IN ('queued','collecting','rendering','publishing')"),
        ),
        CheckConstraint(
            "status IN ('queued','collecting','rendering','publishing','ready','failed')",
            name="ck_report_generation_jobs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evidence_partial: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


@event.listens_for(ReportSnapshotModel, "before_update")
def _reject_snapshot_update(*_args: object) -> None:
    raise ValueError("Report snapshots are immutable; create a new capture")
