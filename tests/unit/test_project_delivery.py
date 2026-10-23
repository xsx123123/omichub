"""RI06–RI09 real SQLite/files/publication, broker replaced: PASS_ISOLATED only."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cygnusx.application.schemas.project_delivery import (
    CreateProjectExport,
    ExportSelection,
    ProjectDeliveryManifest,
)
from cygnusx.application.services import project_delivery_service as module
from cygnusx.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from cygnusx.domain.project_delivery_archive import verify_archive
from cygnusx.infrastructure.config.storage_config import StorageConfig
from cygnusx.infrastructure.database.models.dataset import DatasetIngestionModel
from cygnusx.infrastructure.database.models.download_execution import (
    DownloadExecutionAdmissionModel,
    DownloadExecutionBudgetModel,
)
from cygnusx.infrastructure.database.models.file import DirectoryModel, FileRecordModel
from cygnusx.infrastructure.database.models.project_export import (
    ProjectExportJobModel,
    ProjectExportRequestModel,
)
from cygnusx.infrastructure.database.models.project_report import (
    ProjectReportJobModel,
    ProjectReportRequestModel,
)
from cygnusx.infrastructure.database.models.report import ReportFileModel, ReportModel
from cygnusx.infrastructure.database.models.research_plan import ResearchPlanModel
from cygnusx.infrastructure.database.models.task import TaskModel
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.storage.backend import LocalStorageBackend
from cygnusx.infrastructure.storage.path_factory import StoragePathFactory
from tests.unit.test_dataset_phase3 import registry as registry
from tests.unit.test_report_snapshot import inline_file_capture as inline_file_capture
from tests.unit.test_report_snapshot import synthetic_rna as synthetic_rna
from tests.unit.test_research_delivery_phase4 import delivery as delivery
from tests.unit.test_research_delivery_phase4 import linked

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
async def project_export(delivery, monkeypatch, inline_file_capture):
    db, _, owner, other, project, old_factory, settings = delivery
    # delete_project 预检查覆盖全部科研保留引用表，测试库需一并建齐；
    # checkfirst：下游 fixture（claim_env 等）可能在同一引擎上重复建表
    for model in (
        ProjectExportJobModel,
        ProjectExportRequestModel,
        DirectoryModel,
        DatasetIngestionModel,
        ResearchPlanModel,
        DownloadExecutionBudgetModel,
        DownloadExecutionAdmissionModel,
        ProjectReportJobModel,
        ProjectReportRequestModel,
    ):
        model.__table__.create(db.sync.bind, checkfirst=True)

    async def scalars(statement, **kwargs):
        return db.sync.scalars(statement, **kwargs)

    async def refresh(row, **kwargs):
        db.sync.refresh(row, **kwargs)

    async def scalar(statement, **kwargs):
        return db.sync.scalar(statement, **kwargs)

    monkeypatch.setattr(db, "scalars", scalars)
    monkeypatch.setattr(db, "refresh", refresh)
    monkeypatch.setattr(db, "scalar", scalar)
    factory = StoragePathFactory(
        StorageConfig(data_root=str(old_factory.data_root), users_subdir="users")
    )
    backend = LocalStorageBackend(factory)
    settings.project_export_enabled = True
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "get_path_factory", lambda: factory)
    monkeypatch.setattr(module, "get_storage_backend", lambda: backend)
    from cygnusx.infrastructure.storage import file_registry

    monkeypatch.setattr(file_registry, "get_path_factory", lambda: factory)
    monkeypatch.setattr(file_registry, "get_storage_backend", lambda: backend)
    from cygnusx.infrastructure.celery_app.tasks import project_exports

    monkeypatch.setattr(project_exports, "get_settings", lambda: settings)
    dispatch = AsyncMock()
    monkeypatch.setattr(module, "dispatch_export", dispatch)
    task, link, artifact, manifest = await linked(delivery, monkeypatch)
    source = Path(task.work_dir) / "science.html"
    source.write_bytes(b"<html>Existing scientific report</html>")
    report = ReportModel(
        id=uuid4(),
        task_id=task.id,
        user_id=owner,
        flow_id=task.flow_id,
        report_kind="scientific",
        status="completed",
        created_at=datetime.now(UTC),
        version=1,
    )
    db.add(report)
    await db.flush()
    report_file = ReportFileModel(
        report_id=report.id,
        name="science.html",
        type="html",
        path=str(source),
        size=source.stat().st_size,
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    db.add(report_file)
    await db.commit()
    return SimpleNamespace(
        db=db,
        owner=owner,
        other=other,
        project=project,
        task=task,
        report=report,
        file=report_file,
        source=source,
        settings=settings,
        dispatch=dispatch,
        service=module.ProjectDeliveryService(db),
        factory=factory,
        artifact=artifact,
        link=link,
    )


async def create(env, selection=None, request_key=None):
    selection = selection or ExportSelection()
    manifest = await env.service.prepare(env.owner, env.project, selection)
    request = CreateProjectExport(
        selection=selection,
        manifest_digest=manifest.content_digest(),
        request_key=request_key or uuid4(),
    )
    return await env.service.create(env.owner, env.project, request)


async def test_single_project_roundtrip_is_partial_existing_reports_and_no_compute(
    project_export, monkeypatch
):
    env = project_export
    from cygnusx.application.services.download_service import DownloadService
    from cygnusx.application.services.report_service import ReportService
    from cygnusx.application.services.task_service import TaskService

    monkeypatch.setattr(TaskService, "submit", AsyncMock(side_effect=AssertionError("No analysis")))
    monkeypatch.setattr(
        DownloadService, "submit", AsyncMock(side_effect=AssertionError("No download"))
    )
    monkeypatch.setattr(
        ReportService,
        "build_delivery_package",
        AsyncMock(side_effect=AssertionError("No implicit rendering")),
    )
    job = await create(env)
    frozen = json.dumps(job.manifest, sort_keys=True)
    await module.run_project_export(env.db, job.id)
    assert job.status == "ready" and job.file_record_id
    data = await env.service.download(env.owner, env.project, job.id)
    assert hashlib.sha256(data).hexdigest() == job.archive_sha256
    document = verify_archive(io.BytesIO(data))
    assert document["manifest"]["evidence_status"] == "partial"
    assert document["manifest"]["reproduction_status"] == "NOT_RUN"
    assert any("REPORT_SNAPSHOT_MISSING" in g for g in document["manifest"]["gaps"])
    assert any("REPRODUCIBILITY_REPORT_MISSING" in g for g in document["manifest"]["gaps"])
    assert json.dumps(job.manifest, sort_keys=True) == frozen
    record = await env.db.get(FileRecordModel, job.file_record_id)
    assert record.task_id is None and record.checksum == job.archive_sha256
    assert env.db.sync.query(TaskModel).count() == 1
    assert env.db.sync.query(ReportModel).count() == 1
    assert not any("fastq" in f["path"].lower() for f in document["manifest"]["files"])


async def test_multiple_datasets_tasks_report_versions_and_explicit_selection(
    project_export, delivery, monkeypatch
):
    env = project_export
    # Original fixture uses a fixed path; remove only fixture manifest directory before a second synthetic task.
    from cygnusx.application.schemas.dataset import DatasetCreate
    from cygnusx.infrastructure.database.models.dataset import (
        DatasetAnalysisLinkModel,
        DatasetVersionModel,
    )

    datasets = delivery[1]
    dataset = await datasets.create(
        env.owner, env.project, DatasetCreate(name="second", assay_type="bulk_rnaseq")
    )
    version = env.db.sync.query(DatasetVersionModel).filter_by(dataset_id=dataset.id).one()
    task = TaskModel(
        id=uuid4(), user_id=env.owner, flow_id="counts_deg", status="failed", parameters={}
    )
    env.db.add(task)
    env.db.add(
        DatasetAnalysisLinkModel(
            id=uuid4(),
            version_id=version.id,
            task_id=task.id,
            flow_id=task.flow_id,
            handoff_hash="a" * 64,
            parameters_hash="b" * 64,
            normalized_request={"owner_id": str(env.owner), "project_id": str(env.project)},
            state="QUEUED",
        )
    )
    report = ReportModel(
        id=uuid4(),
        user_id=env.owner,
        task_id=env.task.id,
        flow_id="counts_deg",
        report_kind="scientific",
        status="completed",
        created_at=datetime.now(UTC),
        version=2,
        parent_id=env.report.id,
    )
    env.db.add(report)
    await env.db.commit()
    manifest = await env.service.prepare(env.owner, env.project, ExportSelection())
    assert set(manifest.selection.task_ids) == {env.task.id, task.id}
    assert {r.id for r in manifest.references if r.kind == "report"} >= {report.id, env.report.id}
    assert len({r.id for r in manifest.references if r.kind == "dataset_version"}) == 2
    only = await env.service.prepare(
        env.owner,
        env.project,
        ExportSelection(task_ids=(env.task.id,), report_ids=(env.report.id,)),
    )
    assert only.selection.task_ids == (env.task.id,)
    assert {r.id for r in only.references if r.kind == "report"} == {env.report.id}


async def test_missing_scientific_and_evidence_reports_export_explicit_gaps(project_export):
    env = project_export
    env.db.sync.delete(env.file)
    env.db.sync.delete(env.report)
    await env.db.commit()
    manifest = await env.service.prepare(env.owner, env.project, ExportSelection())
    assert any("SCIENTIFIC_REPORT_MISSING" in g for g in manifest.gaps)
    assert any("REPRODUCIBILITY_REPORT_MISSING" in g for g in manifest.gaps)
    assert len(manifest.files) == 2


async def test_orphan_task_never_inferred_from_same_path_or_name(project_export):
    env = project_export
    orphan = TaskModel(
        id=uuid4(),
        user_id=env.owner,
        flow_id=env.task.flow_id,
        status="success",
        work_dir=env.task.work_dir,
        parameters={},
    )
    env.db.add(orphan)
    await env.db.commit()
    manifest = await env.service.prepare(env.owner, env.project, ExportSelection())
    assert orphan.id not in manifest.selection.task_ids
    with pytest.raises(NotFoundError):
        await env.service.prepare(env.owner, env.project, ExportSelection(task_ids=(orphan.id,)))


async def test_cross_owner_project_and_revocation(project_export):
    env = project_export
    job = await create(env)
    for owner, project in ((env.other, env.project), (env.owner, uuid4())):
        with pytest.raises(NotFoundError):
            await env.service.job(owner, project, job.id)
    await module.run_project_export(env.db, job.id)
    user = await env.db.get(UserModel, env.owner)
    user.disabled_modules = ["reports"]
    await env.db.commit()
    with pytest.raises(AuthorizationError):
        await env.service.download(env.owner, env.project, job.id)


async def test_request_key_and_content_dedupe_database_constraints(project_export):
    env = project_export
    key = uuid4()
    first = await create(env, request_key=key)
    assert (await create(env, request_key=key)).id == first.id
    assert (await create(env)).id == first.id
    duplicate = ProjectExportJobModel(
        user_id=env.owner,
        project_id=env.project,
        request_key=str(uuid4()),
        manifest_digest=first.manifest_digest,
        manifest=first.manifest,
        status="queued",
    )
    env.db.add(duplicate)
    with pytest.raises(IntegrityError):
        await env.db.commit()
    await env.db.rollback()
    assert env.db.sync.query(ProjectExportJobModel).count() == 1


@pytest.mark.parametrize("phase", ["preview", "worker", "download"])
async def test_drift_rejected_at_each_boundary(project_export, phase):
    env = project_export
    manifest = await env.service.prepare(env.owner, env.project, ExportSelection())
    request = CreateProjectExport(
        selection=ExportSelection(), manifest_digest=manifest.content_digest(), request_key=uuid4()
    )
    if phase == "preview":
        env.source.write_bytes(b"changed")
        with pytest.raises(ConflictError):
            await env.service.create(env.owner, env.project, request)
        assert env.db.sync.query(ProjectExportJobModel).count() == 0
        return
    job = await env.service.create(env.owner, env.project, request)
    if phase == "worker":
        env.source.write_bytes(b"changed")
        with pytest.raises(ConflictError):
            await module.run_project_export(env.db, job.id)
        return
    await module.run_project_export(env.db, job.id)
    (env.factory.data_root / job.archive_path).write_bytes(b"changed")
    with pytest.raises(ConflictError):
        await env.service.download(env.owner, env.project, job.id)


async def test_budgets_truncation_and_safe_file_policy(project_export, monkeypatch):
    env = project_export
    env.settings.project_export_file_max_bytes = 8
    with pytest.raises(ValidationError):
        await env.service.prepare(env.owner, env.project, ExportSelection())
    env.settings.project_export_file_max_bytes = 16 * 1024**2
    env.settings.project_export_max_bytes = 8
    with pytest.raises(ValidationError):
        await env.service.prepare(env.owner, env.project, ExportSelection())
    monkeypatch.setattr(env.service, "inventory", AsyncMock(return_value={"truncated": True}))
    with pytest.raises(ValidationError):
        await env.service.prepare(env.owner, env.project, ExportSelection())


async def test_failure_recovery_reuses_frozen_scope_and_path(project_export, monkeypatch):
    env = project_export
    from cygnusx.application.services import report_archive
    from cygnusx.infrastructure.celery_app.tasks.project_exports import record_failure

    original = report_archive.publish_archive
    monkeypatch.setattr(
        report_archive, "publish_archive", AsyncMock(side_effect=OSError("storage unavailable"))
    )
    job = await create(env)
    with pytest.raises(OSError) as caught:
        await module.run_project_export(env.db, job.id)
    path = job.archive_path
    digest = job.manifest_digest
    await record_failure(env.db, job.id, caught.value)
    assert job.status == "failed" and job.retryable
    monkeypatch.setattr(report_archive, "publish_archive", original)
    await module.run_project_export(env.db, job.id)
    assert job.status == "ready" and job.attempt_count == 2
    assert job.manifest_digest == digest and job.archive_path == path
    file = job.file_record_id
    await module.run_project_export(env.db, job.id)
    assert job.file_record_id == file and job.attempt_count == 2


async def test_zip_hostile_members_rejected(project_export):
    env = project_export
    job = await create(env)
    await module.run_project_export(env.db, job.id)
    data = await env.service.download(env.owner, env.project, job.id)
    for name in ("../escape", "/absolute", "README.md", "undeclared.txt"):
        output = io.BytesIO(data)
        with zipfile.ZipFile(output, "a") as archive:
            archive.writestr(name, b"hostile")
        with pytest.raises(ValueError):
            verify_archive(io.BytesIO(output.getvalue()))
    with pytest.raises(ValueError):
        verify_archive(io.BytesIO(data), max_bytes=10)


async def test_frozen_manifest_guard_and_disabled_gate(project_export):
    env = project_export
    job = await create(env)
    job.manifest_digest = "0" * 64
    with pytest.raises(ValueError):
        await env.db.commit()
    await env.db.rollback()
    env.settings.project_export_enabled = False
    with pytest.raises(AuthorizationError):
        await create(env)


async def test_manifest_schema_and_canonical_stability(project_export):
    env = project_export
    first = await env.service.prepare(env.owner, env.project, ExportSelection())
    second = await env.service.prepare(env.owner, env.project, ExportSelection())
    assert first.content_digest() == second.content_digest()
    assert ProjectDeliveryManifest.model_validate_json(first.model_dump_json()) == first
    assert (
        json.loads(Path("docs/contracts/cygnusx-project-delivery-v1.schema.json").read_text())  # noqa: ASYNC240
        == ProjectDeliveryManifest.model_json_schema()
    )


async def test_existing_snapshot_and_single_task_manifest_reused_without_renderer(
    project_export, synthetic_rna
):
    from cygnusx.application.schemas.report_snapshot import freeze_snapshot
    from cygnusx.application.services.research_delivery_service import (
        DeliveryInput,
        ResearchDeliveryBuilder,
    )
    from cygnusx.infrastructure.database.models.report import ReportSnapshotModel

    env = project_export
    snapshot = await synthetic_rna.build()
    source = snapshot.source_execution.model_copy(
        update={"owner_id": env.owner, "task_id": env.task.id}
    )
    snapshot = freeze_snapshot(
        snapshot.model_copy(update={"source_execution": source, "snapshot_digest": None})
    )
    row = ReportSnapshotModel(
        id=uuid4(),
        task_id=env.task.id,
        user_id=env.owner,
        schema_version=snapshot.schema_version,
        snapshot_digest=snapshot.snapshot_digest,
        payload=snapshot.model_dump(mode="json"),
        captured_at=datetime.now(UTC),
    )
    env.db.add(row)
    await env.db.flush()
    evidence_path = env.source.parent / "evidence.html"
    evidence_path.write_bytes(b"<html>Existing frozen evidence</html>")
    evidence = ReportModel(
        id=uuid4(),
        user_id=env.owner,
        task_id=env.task.id,
        flow_id=env.task.flow_id,
        report_kind="reproducibility",
        status="completed",
        snapshot_id=row.id,
        created_at=datetime.now(UTC),
        version=1,
    )
    env.db.add(evidence)
    await env.db.flush()
    env.db.add(
        ReportFileModel(
            report_id=evidence.id,
            name="evidence.html",
            path=str(evidence_path),
            type="html",
            size=evidence_path.stat().st_size,
            sha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        )
    )
    built = ResearchDeliveryBuilder().build(
        snapshot=snapshot,
        snapshot_id=row.id,
        output_root=env.source.parent,
        inputs=(
            DeliveryInput(
                "Scientific_Report.html", env.source.read_bytes(), "html", str(env.report.id)
            ),
            DeliveryInput(
                "Reproducibility_Record.html", evidence_path.read_bytes(), "html", str(evidence.id)
            ),
        ),
    )
    published = ReportModel(
        id=uuid4(),
        user_id=env.owner,
        task_id=env.task.id,
        flow_id=env.task.flow_id,
        report_kind="delivery",
        status="completed",
        snapshot_id=row.id,
        created_at=datetime.now(UTC),
        version=1,
    )
    env.db.add(published)
    await env.db.flush()
    env.db.add(
        ReportFileModel(
            report_id=published.id,
            name="delivery.zip",
            path=str(built.zip_path),
            type="zip",
            size=built.zip_path.stat().st_size,
            sha256=hashlib.sha256(built.zip_path.read_bytes()).hexdigest(),
        )
    )
    await env.db.commit()
    job = await create(env)
    assert any(f["source_kind"] == "report_snapshot" for f in job.manifest["files"])
    assert any(r["kind"] == "evidence_manifest" for r in job.manifest["references"])
    original = json.dumps(row.payload, sort_keys=True)
    await module.run_project_export(env.db, job.id)
    data = await env.service.download(env.owner, env.project, job.id)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        nested = next(f for f in job.manifest["files"] if f["path"].endswith(".zip"))
        assert archive.read(nested["path"]) == built.zip_path.read_bytes()
    assert json.dumps(row.payload, sort_keys=True) == original


async def test_request_alias_is_bound_even_when_identical_content_reuses_job(project_export):
    env = project_export
    first = await create(env)
    alias = uuid4()
    assert (await create(env, request_key=alias)).id == first.id
    manifest = await env.service.prepare(
        env.owner, env.project, ExportSelection(kind="reproduction_materials")
    )
    request = CreateProjectExport(
        selection=manifest.selection, manifest_digest=manifest.content_digest(), request_key=alias
    )
    with pytest.raises(ConflictError):
        await env.service.create(env.owner, env.project, request)


async def test_unavailable_link_is_visible_and_never_guessed(project_export):
    env = project_export
    env.db.sync.delete(env.task)
    await env.db.commit()
    inventory = await env.service.inventory(env.owner, env.project)
    assert inventory["association_status"] == "PARTIAL_ASSOCIATION"
    manifest = await env.service.prepare(env.owner, env.project, ExportSelection())
    assert "LINKED_TASK_UNAVAILABLE" in manifest.gaps
    assert not manifest.selection.task_ids


async def test_quota_and_project_move_rejected_before_publication(project_export):
    from cygnusx.core.exceptions import QuotaExceededError

    env = project_export
    job = await create(env)
    user = await env.db.get(UserModel, env.owner)
    user.storage_quota = 1
    await env.db.commit()
    with pytest.raises(QuotaExceededError):
        await module.run_project_export(env.db, job.id)
    assert job.status != "ready" and job.file_record_id is None


async def test_result_package_includes_registered_small_result_not_raw_input(project_export):
    env = project_export
    from cygnusx.domain.file.value_objects import FileSource
    from cygnusx.infrastructure.storage.file_registry import FileRegistry

    record = await FileRegistry(env.db).register(
        env.owner,
        env.artifact,
        source=FileSource.PIPELINE,
        task_id=env.task.id,
        checksum=hashlib.sha256(env.artifact.read_bytes()).hexdigest(),
    )
    await env.db.commit()
    evidence = await env.service.prepare(env.owner, env.project, ExportSelection())
    results = await env.service.prepare(env.owner, env.project, ExportSelection(kind="results"))
    assert not any(f.source_id == record.id for f in evidence.files)
    assert any(f.source_id == record.id for f in results.files)
    job = await create(env, ExportSelection(kind="results"))
    await module.run_project_export(env.db, job.id)
    assert job.status == "ready"


async def test_rest_preview_human_create_poll_and_download(project_export, monkeypatch):
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from cygnusx.api import deps
    from cygnusx.api.v1.research_delivery import router
    from cygnusx.core.exceptions import CygnusXError

    env = project_export
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def database():
        yield env.db

    async def owner():
        return str(env.owner)

    async def authenticate(token):
        assert token == "human-login"
        return str(env.owner)

    monkeypatch.setattr(deps, "_authenticate_jwt", authenticate)
    app.dependency_overrides[deps.get_db] = database
    app.dependency_overrides[deps.get_current_user_id] = owner

    @app.exception_handler(CygnusXError)
    async def failure(_request: Request, exc: CygnusXError):
        return JSONResponse({"code": exc.code, "detail": exc.detail}, status_code=exc.status_code)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://isolated.test"
    ) as client:
        base = f"/api/v1/projects/{env.project}"
        inventory = await client.get(base + "/delivery-inventory")
        assert inventory.status_code == 200
        preview = (await client.post(base + "/exports/prepare", json={"kind": "evidence"})).json()
        payload = {
            "selection": preview["manifest"]["selection"],
            "manifest_digest": preview["manifest_digest"],
            "request_key": str(uuid4()),
        }
        denied = await client.post(
            base + "/exports", json=payload, headers={"X-API-Key": "model-key"}
        )
        assert denied.status_code == 401
        created = await client.post(
            base + "/exports", json=payload, headers={"Authorization": "Bearer human-login"}
        )
        assert created.status_code == 200, created.text
        job_id = created.json()["id"]
        from uuid import UUID

        await module.run_project_export(env.db, UUID(job_id))
        status = (await client.get(base + f"/exports/{job_id}")).json()
        assert status["status"] == "ready"
        downloaded = await client.get(
            base + f"/exports/{job_id}/download", headers={"Authorization": "Bearer human-login"}
        )
        assert downloaded.status_code == 200
        assert hashlib.sha256(downloaded.content).hexdigest() == status["archive_sha256"]
        assert downloaded.headers["x-content-sha256"] == status["archive_sha256"]
        assert downloaded.headers["cache-control"] == "no-store"


async def test_actual_migration_on_disposable_sqlite_and_unique_scope(project_export):
    import importlib.util

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    env = project_export
    ProjectExportRequestModel.__table__.drop(env.db.sync.bind)
    ProjectExportJobModel.__table__.drop(env.db.sync.bind)
    spec = importlib.util.spec_from_file_location(
        "project_delivery_migration", "alembic/versions/projectdelivery01_project_exports.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with env.db.sync.bind.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert {"project_export_jobs", "project_export_requests"}.issubset(
            inspector.get_table_names()
        )
        assert len(inspector.get_unique_constraints("project_export_jobs")) == 2
    job = await create(env)
    await module.run_project_export(env.db, job.id)
    assert job.status == "ready"


async def test_gateway_exposes_only_read_inventory_report_lookup_and_job_status(project_export):
    from cygnusx.application.schemas.agent_tools import capability_catalog
    from cygnusx.application.services.agent_tool_gateway import AgentToolGateway

    env = project_export
    job = await create(env)
    context = SimpleNamespace(user_id=str(env.owner), extra={"project_id": str(env.project)})
    gateway = AgentToolGateway(env.db)
    result = await gateway._research_tool(context, "research.project_inventory", {})
    assert result == await env.service.inventory(env.owner, env.project)
    status = await gateway._research_tool(
        context, "research.project_export_status", {"job_id": str(job.id)}
    )
    assert status["id"] == str(job.id)
    catalog = capability_catalog(include_research=True)
    exports = [cap for cap in catalog if "project_export" in cap.capability_id]
    assert len(exports) == 1 and exports[0].side_effect == "none"
    assert not any("exports.create" in cap.capability_id for cap in catalog)


async def test_source_symlink_and_raw_result_are_never_included(project_export):
    env = project_export
    original = env.source.read_bytes()
    outside = env.source.parent / "other.html"
    outside.write_bytes(original)
    env.source.unlink()
    env.source.symlink_to(outside)
    partial = await env.service.prepare(env.owner, env.project, ExportSelection())
    assert not any(f.source_id == env.file.id for f in partial.files)
    assert any("REPORT_FILE_UNAVAILABLE" in gap for gap in partial.gaps)
    env.source.unlink()
    env.source.write_bytes(original)
    from cygnusx.infrastructure.storage.file_registry import FileRegistry

    raw = env.artifact.parent / "reads.fastq"
    raw.write_bytes(b"@r\nA\n+\nI\n")
    record = await FileRegistry(env.db).register(
        env.owner, raw, task_id=env.task.id, checksum=hashlib.sha256(raw.read_bytes()).hexdigest()
    )
    manifest_path = raw.parent / "result_manifest.json"
    result = json.loads(manifest_path.read_bytes())
    result["files"].append(
        {"path": "reads.fastq", "sha256": record.checksum, "size_bytes": record.size}
    )
    manifest_path.write_text(json.dumps(result))
    await env.db.commit()
    package = await env.service.prepare(env.owner, env.project, ExportSelection(kind="results"))
    assert not any(f.source_id == record.id for f in package.files)
    assert any(r.id == record.id and r.disposition == "excluded" for r in package.references)


async def test_retained_export_prevents_project_deletion(project_export, monkeypatch):
    env = project_export
    from cygnusx.application.services.project_service import ProjectService
    from cygnusx.core import config

    monkeypatch.setattr(config, "get_settings", lambda: env.settings)
    await create(env)
    service = ProjectService(env.db)
    with pytest.raises(ConflictError, match="保留"):
        await service.delete_project(env.owner, env.project)


async def test_changed_report_metadata_cannot_rebind_frozen_delivery(project_export):
    env = project_export
    job = await create(env)
    env.report.version = 2
    await env.db.commit()
    with pytest.raises(ConflictError, match="association"):
        await module.run_project_export(env.db, job.id)
    assert job.file_record_id is None


def standalone_check(script: Path, archive: Path) -> str:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-I", str(script), str(archive)],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    return result.stdout


async def test_shipped_verifier_runs_without_platform_imports(project_export, tmp_path):
    env = project_export
    job = await create(env)
    await module.run_project_export(env.db, job.id)
    data = await env.service.download(env.owner, env.project, job.id)
    script = tmp_path / "verify_project_delivery.py"
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        script.write_bytes(package.read("verify_project_delivery.py"))
    output = standalone_check(script, env.factory.data_root / job.archive_path)
    assert "PASS" in output and "NOT_RUN" in output
