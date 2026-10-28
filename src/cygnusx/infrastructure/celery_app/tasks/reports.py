"""Bounded report delivery with a durable outbox and per-Task PostgreSQL lock."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from celery import shared_task
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from cygnusx.infrastructure.database.models.report import ReportGenerationJobModel

TASK_PREFIX = "cygnusx.infrastructure.celery_app.tasks.reports"


@shared_task(name=f"{TASK_PREFIX}.import_flow_reports", soft_time_limit=600, time_limit=660)  # type: ignore[untyped-decorator]
def import_flow_reports() -> dict[str, int]:
    return asyncio.run(_import_flow_reports())


async def _import_flow_reports() -> dict[str, int]:
    from cygnusx.application.services.flow_report_import_service import FlowReportImportService
    from cygnusx.infrastructure.database.session import create_unpooled_engine

    if not get_settings().flow_report_import_enabled:
        return {"imported": 0, "unchanged": 0, "failed": 0}
    engine = create_unpooled_engine()
    try:
        async with engine.connect() as connection, AsyncSession(bind=connection, expire_on_commit=False) as db:
            key = task_lock_key(UUID(int=0))
            locked = await db.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            await db.commit()
            if not locked:
                return {"busy": 1}
            try:
                async with asyncio.timeout(590):
                    return await FlowReportImportService(db).scan()
            finally:
                await db.rollback()
                await db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                await db.commit()
    finally:
        await engine.dispose()


def task_lock_key(task_id: UUID) -> int:
    return int.from_bytes(hashlib.sha256(f"report:{task_id}".encode()).digest()[:8], signed=True)


def failure_details(exc: Exception) -> tuple[str, str, bool]:
    """Public codes/messages are constants; never export raw exceptions or credentials."""
    if isinstance(exc, AuthorizationError):
        return "evidence_forbidden", "证据访问权限校验失败，请联系管理员。", False
    if isinstance(exc, NotFoundError):
        return "source_unavailable", "任务或已发布报告不可用，请检查来源记录。", False
    if isinstance(exc, ConflictError):
        return "evidence_conflict", "证据关联或完整性校验失败，请检查来源记录。", False
    if isinstance(exc, (ValidationError, ValueError)):
        return "invalid_evidence", "证据或快照格式无效，请联系管理员。", False
    from cygnusx.application.services.bioreport_adapter import BioReportRenderError

    if isinstance(exc, BioReportRenderError):
        return "scientific_render_failed", "科学报告渲染失败，可独立重试。", True
    if isinstance(exc, (OSError, TimeoutError)):
        return "storage_or_timeout", "文件读写失败或证据采集超时，可安全重试。", True
    from sqlalchemy.exc import DBAPIError

    if isinstance(exc, DBAPIError):
        return "database_unavailable", "报告登记暂时失败，可安全重试。", True
    return "generation_failed", "报告生成失败，请联系管理员。", False


async def record_failure(db: AsyncSession, job_id: UUID, exc: Exception) -> None:
    await db.rollback()
    job = await db.get(ReportGenerationJobModel, job_id)
    if job is not None and job.status != "ready":
        job.error_code, job.error_message, retryable = failure_details(exc)
        job.retryable = (
            retryable and job.attempt_count < get_settings().report_generation_max_attempts
        )
        job.status = "failed"
        job.finished_at = datetime.now(UTC)
        job.updated_at = job.finished_at
        await db.commit()


@shared_task(  # type: ignore[untyped-decorator]
    name=f"{TASK_PREFIX}.generate_reproducible_report",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=1900,
    time_limit=1950,
)
def generate_reproducible_report(job_id: str) -> dict[str, str]:
    return asyncio.run(_run(UUID(job_id)))


async def _run(job_id: UUID) -> dict[str, str]:
    from cygnusx.application.services.reproducible_report_service import run_reproducible_report
    from cygnusx.infrastructure.database.session import create_unpooled_engine

    engine = create_unpooled_engine()
    try:
        # A dedicated connection is essential: session advisory locks must not be
        # returned to a pool or lost when a status transaction commits.
        async with (
            engine.connect() as connection,
            AsyncSession(bind=connection, expire_on_commit=False) as db,
        ):
            job = await db.get(ReportGenerationJobModel, job_id)
            if job is None:
                return {"job_id": str(job_id), "status": "missing"}
            key = task_lock_key(job.task_id)
            locked = await db.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            await db.commit()
            if not locked:
                return {"job_id": str(job_id), "status": "busy"}
            try:
                # Refresh after acquiring the lock: a previous delivery may have
                # published while this consumer waited for a connection.
                await db.refresh(job)
                try:
                    async with asyncio.timeout(get_settings().report_generation_timeout_seconds):
                        await run_reproducible_report(db, job_id)
                except Exception as exc:
                    await record_failure(db, job_id, exc)
                await db.refresh(job)
                return {"job_id": str(job_id), "status": job.status}
            finally:
                await db.rollback()
                await db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                await db.commit()
    finally:
        await engine.dispose()


@shared_task(name=f"{TASK_PREFIX}.reconcile_report_jobs")  # type: ignore[untyped-decorator]
def reconcile_report_jobs() -> dict[str, int]:
    return asyncio.run(_reconcile())


async def _reconcile() -> dict[str, int]:
    from cygnusx.application.services.reproducible_report_service import (
        ACTIVE_STATUSES,
        dispatch_report_job,
    )
    from cygnusx.infrastructure.database.session import create_unpooled_engine

    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.report_generation_reconcile_seconds)
    stale = datetime.now(UTC) - timedelta(seconds=settings.report_generation_timeout_seconds + 60)
    engine = create_unpooled_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            ids = list(
                (
                    await db.scalars(
                        select(ReportGenerationJobModel.id)
                        .where(
                            or_(
                                (ReportGenerationJobModel.status == "queued")
                                & (ReportGenerationJobModel.updated_at < cutoff),
                                (ReportGenerationJobModel.status.in_(ACTIVE_STATUSES))
                                & (ReportGenerationJobModel.updated_at < stale),
                                (ReportGenerationJobModel.status == "failed")
                                & ReportGenerationJobModel.retryable
                                & (ReportGenerationJobModel.updated_at < cutoff),
                            )
                        )
                        .order_by(ReportGenerationJobModel.updated_at)
                        .limit(100)
                    )
                ).all()
            )
        for job_id in ids:
            await dispatch_report_job(job_id)
        return {"dispatched": len(ids)}
    finally:
        await engine.dispose()
