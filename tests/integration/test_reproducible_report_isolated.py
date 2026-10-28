"""Isolated delivery integration: real SQLite ORM, synthetic RNA files and ASGI APIs.

SQLite is driven synchronously to avoid unavailable executor wakeup sockets. This
suite does not prove PostgreSQL advisory locking, live Celery or a real RNA run.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cygnusx.api.deps import get_current_user_id, get_db
from cygnusx.api.v1 import reports, tasks
from cygnusx.application.services.report_service import ReportService
from cygnusx.application.services.reproducible_report_service import (
    ReproducibleReportService,
    run_reproducible_report,
)
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import ConflictError, CygnusXError, NotFoundError
from cygnusx.infrastructure.celery_app.tasks.reports import record_failure
from cygnusx.infrastructure.database.models.file import DirectoryModel, FileRecordModel
from cygnusx.infrastructure.database.models.report import (
    ReportFileModel,
    ReportGenerationJobModel,
    ReportModel,
    ReportSnapshotModel,
)
from cygnusx.infrastructure.database.models.run import RunModel
from cygnusx.infrastructure.database.models.run_event import RunEventModel
from cygnusx.infrastructure.database.models.task import TaskModel
from cygnusx.infrastructure.storage.backend import LocalStorageBackend
from tests.unit.test_report_snapshot import SyntheticRNA
from tests.unit.test_report_snapshot import inline_file_capture as inline_file_capture
from tests.unit.test_report_snapshot import synthetic_rna as synthetic_rna

pytestmark = pytest.mark.integration


class AwaitableSession:
    """Execute real ORM queries and constraints, without an async SQLite dependency."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.states: list[str] = []

    @property
    def no_autoflush(self) -> Any:
        return self.session.no_autoflush

    def add(self, value: object) -> None:
        self.session.add(value)

    async def scalar(self, query: Any, *args: Any, **kwargs: Any) -> Any:
        return self.session.scalar(query, *args, **kwargs)

    async def scalars(self, query: Any) -> Any:
        return self.session.scalars(query)

    async def execute(self, query: Any) -> Any:
        if str(query).startswith("SET TRANSACTION"):
            # PostgreSQL-only repeatable-read syntax is deliberately NOT simulated.
            return None
        return self.session.execute(query)

    async def get(self, model: Any, key: Any) -> Any:
        return self.session.get(model, key)

    async def flush(self) -> None:
        self.session.flush()

    async def commit(self) -> None:
        self.session.commit()
        self.states.extend(
            obj.status
            for obj in self.session.identity_map.values()
            if isinstance(obj, ReportGenerationJobModel)
        )

    async def rollback(self) -> None:
        self.session.rollback()

    async def refresh(self, obj: Any, **kwargs: Any) -> None:
        self.session.refresh(obj, **kwargs)

    async def delete(self, obj: Any) -> None:
        self.session.delete(obj)


@pytest.fixture
def isolated_db(
    synthetic_rna: SyntheticRNA, monkeypatch: pytest.MonkeyPatch
) -> Iterator[AwaitableSession]:
    # This fixture covers the legacy Task report contract, without Dataset/user
    # tables. Do not inherit optional research-delivery enablement from a local .env.
    monkeypatch.setattr(get_settings(), "research_delivery_read_enabled", False)
    engine = create_engine("sqlite://")
    selected = (
        TaskModel,
        RunModel,
        RunEventModel,
        FileRecordModel,
        DirectoryModel,
        ReportSnapshotModel,
        ReportModel,
        ReportFileModel,
        ReportGenerationJobModel,
    )
    # Only the two Run JSONB columns need SQLite type adaptation; production metadata
    # is restored by monkeypatch. No schema from an external database is changed.
    from sqlalchemy import JSON, DateTime, TypeDecorator

    class SQLiteUTC(TypeDecorator):
        impl = DateTime
        cache_ok = True

        def process_result_value(self, value: Any, dialect: Any) -> Any:
            return (
                value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value
            )

    from sqlalchemy.dialects.postgresql import JSONB

    for model in selected:
        for column in model.__table__.columns:
            if isinstance(column.type, JSONB):
                monkeypatch.setattr(column, "type", JSON())
            elif isinstance(column.type, DateTime) and column.type.timezone:
                monkeypatch.setattr(column, "type", SQLiteUTC(timezone=True))
        model.__table__.create(engine)
    session = Session(engine, expire_on_commit=False)
    session.add(synthetic_rna.records.task)
    session.commit()
    pf = synthetic_rna.factory
    backend = LocalStorageBackend(pf)
    monkeypatch.setattr(
        "cygnusx.application.services.reproducible_report_service.get_path_factory", lambda: pf
    )
    monkeypatch.setattr(
        "cygnusx.application.services.reproducible_report_service.get_storage_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "cygnusx.application.services.reproducible_report_service.dispatch_report_job", AsyncMock()
    )
    monkeypatch.setattr("cygnusx.application.services.report_service.get_path_factory", lambda: pf)
    monkeypatch.setattr(
        "cygnusx.application.services.report_service.get_storage_backend", lambda: backend
    )
    db = AwaitableSession(session)
    try:
        yield db
    finally:
        session.close()
        engine.dispose()


def as_async(db: AwaitableSession) -> AsyncSession:
    return cast(AsyncSession, db)


@pytest.mark.asyncio
async def test_task_snapshot_html_reports_download_and_dedup(
    isolated_db: AwaitableSession, synthetic_rna: SyntheticRNA
) -> None:
    db = as_async(isolated_db)
    owner, task_id = synthetic_rna.owner, synthetic_rna.records.task.id
    service = ReproducibleReportService(db)
    request = uuid4()
    job = await service.enqueue(str(owner), task_id, request_key=request)
    assert job.status == "queued"
    assert (await service.enqueue(str(owner), task_id)).id == job.id
    await run_reproducible_report(db, job.id)
    ready = await service.get_job(str(owner), job.id)
    assert ready.status == "ready" and ready.report_id and ready.snapshot_id
    assert ready.evidence_partial and ready.finished_at
    assert all(
        stage in isolated_db.states for stage in ("collecting", "rendering", "publishing", "ready")
    )
    assert (await service.enqueue(str(owner), task_id, request_key=request)).id == job.id
    report_service = ReportService(db)
    report = await report_service.get_report(ready.report_id, str(owner))
    assert report.report_kind == "reproducibility" and report.version == 1
    assert report.flow_version == ""  # no substitution with current catalog version
    assert report.files[0].sha256 and report.files[0].path == "output/index.html"
    html = await report_service.preview_html(report.id, str(owner))
    assert str(task_id) in html and "not_run" in html
    path = await report_service.download_file(report.id, report.files[0].id, str(owner))
    assert path.read_bytes() == html.encode()
    assert path.is_relative_to(synthetic_rna.factory.projects_dir(str(owner)))
    assert str(task_id) not in str(path)
    assert list(isolated_db.session.scalars(select(DirectoryModel)))
    records = list(isolated_db.session.scalars(select(FileRecordModel)))
    assert len(records) == 1 and records[0].source == "report" and records[0].task_id is None
    frozen = await service.get_snapshot_for_report(str(owner), report.id)
    second = await service.enqueue(str(owner), task_id)
    await run_reproducible_report(db, second.id)
    assert (await service.get_job(str(owner), second.id)).report_id == report.id
    assert len(list(isolated_db.session.scalars(select(ReportModel)))) == 1
    # Real byte change without a Task updated_at change must produce a new version.
    (synthetic_rna.deliver / "counts.tsv").write_bytes(b"gene\tcount\ng1\t99\n")
    third = await service.enqueue(str(owner), task_id)
    await run_reproducible_report(db, third.id)
    final = await service.get_job(str(owner), third.id)
    assert final.report_id != report.id
    new_report = await report_service.get_report(final.report_id, str(owner))
    assert new_report.version == 2 and new_report.parent_id == report.id
    assert (await service.get_snapshot_for_report(str(owner), report.id)).payload == frozen.payload
    assert path.read_bytes() == html.encode()
    assert synthetic_rna.records.task.status == "completed"


@pytest.mark.asyncio
async def test_failure_retries_frozen_snapshot_and_recovers_publication(
    isolated_db: AwaitableSession,
    synthetic_rna: SyntheticRNA,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = as_async(isolated_db)
    service = ReproducibleReportService(db)
    job = await service.enqueue(str(synthetic_rna.owner), synthetic_rna.records.task.id)
    from cygnusx.application.services.report_archive import publish_archive

    original_write = publish_archive
    monkeypatch.setattr(
        "cygnusx.application.services.reproducible_report_service.publish_archive",
        AsyncMock(side_effect=OSError("secret")),
    )
    with pytest.raises(OSError) as failure:
        await run_reproducible_report(db, job.id)
    await record_failure(db, job.id, failure.value)
    failed = await service.get_job(str(synthetic_rna.owner), job.id)
    assert failed.status == "failed" and failed.retryable and failed.snapshot_id
    snapshot = isolated_db.session.get(ReportSnapshotModel, failed.snapshot_id)
    old_digest = snapshot.snapshot_digest
    assert not list(isolated_db.session.scalars(select(ReportModel)))
    # New source facts do not mutate the snapshot selected by a failed publication.
    (synthetic_rna.deliver / "counts.tsv").write_bytes(b"new source data")
    monkeypatch.setattr(
        "cygnusx.application.services.reproducible_report_service.publish_archive", original_write
    )
    retried = await service.retry(str(synthetic_rna.owner), job.id)
    assert retried.snapshot_id == failed.snapshot_id and retried.status == "queued"
    await run_reproducible_report(db, job.id)
    ready = await service.get_job(str(synthetic_rna.owner), job.id)
    assert ready.status == "ready" and ready.attempt_count == 2
    assert snapshot.snapshot_digest == old_digest
    await run_reproducible_report(db, job.id)
    assert len(list(isolated_db.session.scalars(select(ReportModel)))) == 1


@pytest.mark.asyncio
async def test_access_integrity_deletion_and_immutable_snapshot(
    isolated_db: AwaitableSession,
    synthetic_rna: SyntheticRNA,
) -> None:
    db = as_async(isolated_db)
    service = ReproducibleReportService(db)
    job = await service.enqueue(str(synthetic_rna.owner), synthetic_rna.records.task.id)
    await run_reproducible_report(db, job.id)
    ready = await service.get_job(str(synthetic_rna.owner), job.id)
    reports_service = ReportService(db)
    report = await reports_service.get_report(ready.report_id, str(synthetic_rna.owner))
    other = str(uuid4())
    with pytest.raises(NotFoundError):
        await reports_service.preview_html(report.id, other)
    with pytest.raises(NotFoundError):
        await reports_service.download_file(report.id, report.files[0].id, other)
    with pytest.raises(NotFoundError):
        await service.get_snapshot_for_report(other, report.id)
    with pytest.raises(NotFoundError):
        await reports_service.download_file(report.id, uuid4(), str(synthetic_rna.owner))
    path = await reports_service.download_file(
        report.id, report.files[0].id, str(synthetic_rna.owner)
    )
    original = path.read_bytes()
    path.write_bytes(b"<script>malicious()</script>")
    with pytest.raises(ConflictError):
        await reports_service.preview_html(report.id, str(synthetic_rna.owner))
    with pytest.raises(ConflictError):
        await reports_service.download_file(report.id, report.files[0].id, str(synthetic_rna.owner))
    path.write_bytes(original)
    path.unlink()
    with pytest.raises(NotFoundError):
        await reports_service.preview_html(report.id, str(synthetic_rna.owner))
    snapshot = isolated_db.session.get(ReportSnapshotModel, ready.snapshot_id)
    snapshot.payload = {"tampered": True}
    with pytest.raises(ValueError, match="immutable"):
        await db.flush()
    await db.rollback()
    await reports_service.delete_report(report.id, str(synthetic_rna.owner))
    await db.commit()
    with pytest.raises(NotFoundError):
        await service.get_snapshot_for_report(str(synthetic_rna.owner), report.id)


@pytest.mark.asyncio
async def test_asgi_task_request_poll_snapshot_preview_and_download(
    isolated_db: AwaitableSession,
    synthetic_rna: SyntheticRNA,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import anyio.to_thread

    async def inline(function: Any, *args: Any, **kwargs: Any) -> Any:
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", inline)
    db = as_async(isolated_db)
    app = FastAPI()
    app.include_router(tasks.router, prefix="/api/v1/tasks")
    app.include_router(reports.router, prefix="/api/v1/reports")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user_id] = lambda: str(synthetic_rna.owner)

    @app.exception_handler(CygnusXError)
    async def error_handler(_request: Any, exc: CygnusXError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    async with AsyncClient(transport=ASGITransport(app), base_url="http://isolated") as client:
        response = await client.post(
            f"/api/v1/tasks/{synthetic_rna.records.task.id}/reproducibility-reports"
        )
        assert response.status_code == 202
        job_id = UUID(response.json()["id"])
        await run_reproducible_report(db, job_id)
        polled = await client.get(f"/api/v1/reports/jobs/{job_id}")
        assert polled.json()["status"] == "ready"
        report_id = polled.json()["report_id"]
        detail = await client.get(f"/api/v1/reports/{report_id}")
        file_id = detail.json()["files"][0]["id"]
        snapshot = await client.get(f"/api/v1/reports/{report_id}/snapshot")
        assert snapshot.json()["payload"]["source_execution"]["task_id"] == str(
            synthetic_rna.records.task.id
        )
        preview = await client.get(f"/api/v1/reports/{report_id}/preview")
        downloaded = await client.get(f"/api/v1/reports/{report_id}/files/{file_id}/download")
        assert downloaded.status_code == 200 and downloaded.content == preview.content
        assert "attachment" in downloaded.headers["content-disposition"]
        assert (
            await client.post("/api/v1/tasks/invalid/reproducibility-reports")
        ).status_code == 422
        app.dependency_overrides[get_current_user_id] = lambda: str(uuid4())
        assert (await client.get(f"/api/v1/reports/{report_id}/snapshot")).status_code == 404
        assert (
            await client.get(f"/api/v1/reports/{report_id}/files/{file_id}/download")
        ).status_code == 404
        assert (
            await client.post(
                f"/api/v1/tasks/{synthetic_rna.records.task.id}/reproducibility-reports"
            )
        ).status_code == 404


@pytest.mark.asyncio
async def test_active_and_published_uniqueness_are_database_enforced(
    isolated_db: AwaitableSession,
    synthetic_rna: SyntheticRNA,
) -> None:
    from sqlalchemy.exc import IntegrityError

    db = as_async(isolated_db)
    service = ReproducibleReportService(db)
    job = await service.enqueue(str(synthetic_rna.owner), synthetic_rna.records.task.id)
    conflicting = ReportGenerationJobModel(
        id=uuid4(),
        task_id=job.task_id,
        user_id=synthetic_rna.owner,
        idempotency_key="conflicting-delivery",
        template_version=job.template_version,
        status="queued",
        error_message="",
        retryable=False,
        evidence_partial=True,
        attempt_count=0,
    )
    isolated_db.session.add(conflicting)
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()
    await run_reproducible_report(db, job.id)
    ready = await service.get_job(str(synthetic_rna.owner), job.id)
    original = isolated_db.session.get(ReportModel, ready.report_id)
    clone = ReportModel(
        id=uuid4(),
        task_id=job.task_id,
        user_id=synthetic_rna.owner,
        flow_id="rna_seq",
        title="duplicate",
        status="completed",
        created_at=datetime.now(UTC),
        snapshot_id=original.snapshot_id,
        template_version=original.template_version,
        report_kind="reproducibility",
    )
    isolated_db.session.add(clone)
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_registration_failure_preserves_private_bytes_for_retry(
    isolated_db: AwaitableSession,
    synthetic_rna: SyntheticRNA,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = as_async(isolated_db)
    service = ReproducibleReportService(db)
    job = await service.enqueue(str(synthetic_rna.owner), synthetic_rna.records.task.id)
    original = ReportService.register_reproducibility_report
    monkeypatch.setattr(
        ReportService,
        "register_reproducibility_report",
        AsyncMock(side_effect=OSError("registration interrupted")),
    )
    with pytest.raises(OSError) as failure:
        await run_reproducible_report(db, job.id)
    await record_failure(db, job.id, failure.value)
    stored_job = isolated_db.session.get(ReportGenerationJobModel, job.id)
    path = synthetic_rna.factory.data_root / stored_job.archive_path
    before = path.read_bytes()
    assert stored_job.status == "failed" and stored_job.snapshot_id
    assert not list(isolated_db.session.scalars(select(ReportModel)))
    assert not list(isolated_db.session.scalars(select(FileRecordModel)))
    monkeypatch.setattr(ReportService, "register_reproducibility_report", original)
    await service.retry(str(synthetic_rna.owner), job.id)
    await run_reproducible_report(db, job.id)
    assert (await service.get_job(str(synthetic_rna.owner), job.id)).status == "ready"
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_commit_precedes_dispatch_and_deleted_report_is_not_ready(
    isolated_db: AwaitableSession,
    synthetic_rna: SyntheticRNA,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = as_async(isolated_db)
    service = ReproducibleReportService(db)

    async def dispatch(job_id: UUID) -> None:
        assert not isolated_db.session.in_transaction()
        assert isolated_db.session.get(ReportGenerationJobModel, job_id) is not None
        await db.commit()

    monkeypatch.setattr(
        "cygnusx.application.services.reproducible_report_service.dispatch_report_job", dispatch
    )
    job = await service.enqueue(str(synthetic_rna.owner), synthetic_rna.records.task.id)
    await run_reproducible_report(db, job.id)
    ready = await service.get_job(str(synthetic_rna.owner), job.id)
    await ReportService(db).delete_report(ready.report_id, str(synthetic_rna.owner))
    await db.commit()
    removed = await service.get_job(str(synthetic_rna.owner), job.id)
    assert removed.status == "failed" and removed.error_code == "report_removed"
