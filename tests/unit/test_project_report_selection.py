"""RI095 SQLite/actual TSV claim freezing; isolated evidence only."""

from uuid import uuid4

import pytest
from pydantic import ValidationError as SchemaError

from cygnusx.application.schemas.project_delivery import ExportSelection
from cygnusx.application.schemas.project_report import PrepareProjectReport, ProjectClaimSelection
from cygnusx.application.services.project_delivery_service import run_project_export
from cygnusx.application.services.project_report_selection import ProjectReportSelectionService
from cygnusx.core.exceptions import ConflictError, NotFoundError
from tests.unit.test_claim_provenance_ri10 import claim_env as claim_env
from tests.unit.test_dataset_phase3 import registry as registry
from tests.unit.test_project_delivery import create
from tests.unit.test_project_delivery import project_export as project_export
from tests.unit.test_report_snapshot import inline_file_capture as inline_file_capture
from tests.unit.test_research_delivery_phase4 import delivery as delivery

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def isolated_report_dispatch(monkeypatch):
    from unittest.mock import AsyncMock

    from cygnusx.application.services import project_report_service

    dispatch = AsyncMock()
    monkeypatch.setattr(project_report_service, "dispatch_project_report", dispatch)
    return dispatch


async def prepare_env(env):
    job = await create(env, ExportSelection(kind="results"))
    await run_project_export(env.db, job.id)
    assert job.status == "ready"
    request = PrepareProjectReport(
        source_manifest_job_id=job.id,
        claims=(ProjectClaimSelection(**env.query.model_dump(exclude={"claim"})),),
    )
    return job, request, ProjectReportSelectionService(env.db)


async def test_real_m0_and_tsv_freeze_is_stable_without_writes(claim_env):
    env = claim_env
    job, request, service = await prepare_env(env)
    original = job.manifest_digest
    source = await service.prepare(env.owner, env.project, request)
    assert source.selection.claims[0].value == 0.03
    assert source.selection.claims[0].file_sha256 == env.sha
    assert source.source_manifest_digest == original
    assert source.renderer_runtime == "NOT_OBSERVED"
    assert (
        await service.confirm(env.owner, env.project, request, source.content_digest())
    ) == source
    assert job.manifest_digest == original
    with pytest.raises(ConflictError, match="prepare again"):
        await service.confirm(env.owner, env.project, request, "0" * 64)
    with pytest.raises(NotFoundError):
        await service.prepare(env.other, env.project, request)


async def test_scope_and_report_selection_fail_closed(claim_env):
    env = claim_env
    _, request, service = await prepare_env(env)
    for field in ("task_id", "file_record_id", "source_report_id"):
        cell = request.claims[0].model_copy(update={field: uuid4()})
        with pytest.raises(NotFoundError):
            await service.prepare(
                env.owner, env.project, request.model_copy(update={"claims": (cell,)})
            )


async def test_empty_claims_and_na_are_honest(claim_env):
    env = claim_env
    _, request, service = await prepare_env(env)
    empty = await service.prepare(env.owner, env.project, request.model_copy(update={"claims": ()}))
    assert empty.selection.claims == ()
    cell = request.claims[0].model_copy(update={"column": "padj"})
    source = await service.prepare(
        env.owner, env.project, request.model_copy(update={"claims": (cell,)})
    )
    assert source.selection.claims[0].verification_status == "NOT_VERIFIED"
    assert source.selection.claims[0].value is None


async def test_client_facts_and_duplicate_cells_are_rejected(claim_env):
    _, request, _ = await prepare_env(claim_env)
    for field in ("value", "sha256", "owner_id", "project_id", "verification_status", "claim"):
        with pytest.raises(SchemaError):
            ProjectClaimSelection.model_validate(
                {**request.claims[0].model_dump(), field: "forged"}
            )
    with pytest.raises(SchemaError):
        PrepareProjectReport(source_manifest_job_id=uuid4(), claims=request.claims * 2)


async def test_source_byte_drift_rejected(claim_env):
    env = claim_env
    _, request, service = await prepare_env(env)
    source = await service.prepare(env.owner, env.project, request)
    env.artifact.write_text("gene_id\tpvalue\nfixture_gene\t0.9\n")
    from cygnusx.core.exceptions import ValidationError

    with pytest.raises((ConflictError, ValidationError)):
        await service.confirm(env.owner, env.project, request, source.content_digest())


async def test_project_job_constraints_and_frozen_identity(claim_env):
    from sqlalchemy.exc import IntegrityError

    from cygnusx.infrastructure.database.models.project_report import ProjectReportJobModel
    from cygnusx.infrastructure.database.models.report import ReportGenerationJobModel, ReportModel

    env = claim_env
    job, request, service = await prepare_env(env)
    source = await service.prepare(env.owner, env.project, request)
    ProjectReportJobModel.__table__.create(env.db.sync.bind, checkfirst=True)
    record = ProjectReportJobModel(
        user_id=env.owner,
        project_id=env.project,
        source_manifest_job_id=job.id,
        request_key=str(uuid4()),
        source_digest=source.content_digest(),
        source_snapshot=source.model_dump(mode="json"),
    )
    env.db.add(record)
    await env.db.commit()
    record.status = "ready"
    with pytest.raises(IntegrityError):
        await env.db.flush()
    await env.db.rollback()
    record = await env.db.get(ProjectReportJobModel, record.id)
    record.source_digest = "0" * 64
    with pytest.raises(ValueError, match="Frozen"):
        await env.db.flush()
    await env.db.rollback()
    assert not ReportModel.__table__.c.task_id.nullable
    assert not ReportGenerationJobModel.__table__.c.task_id.nullable


async def test_actual_sqlite_migration_guard_and_null_ready_check():
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError

    spec = importlib.util.spec_from_file_location(
        "ri095_migration", "alembic/versions/projectreport01_project_report_jobs.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    connection = engine.connect()
    for table in ("users", "projects", "project_export_jobs", "reports", "file_records"):
        connection.execute(text(f"CREATE TABLE {table} (id CHAR(32) PRIMARY KEY)"))
    connection.execute(
        text(
            "CREATE TABLE report_files (id CHAR(32) PRIMARY KEY, report_id CHAR(32) NOT NULL REFERENCES reports(id))"
        )
    )
    connection.execute(text("INSERT INTO reports VALUES ('old')"))
    connection.execute(text("INSERT INTO report_files VALUES ('old-file', 'old')"))
    migration.op = Operations(MigrationContext.configure(connection))
    migration.upgrade()
    assert (
        connection.scalar(text("SELECT report_id FROM report_files WHERE id='old-file'")) == "old"
    )
    with pytest.raises(IntegrityError):
        connection.execute(text("INSERT INTO report_files(id) VALUES ('invalid')"))
    ids = {key: uuid4().hex for key in ("id", "owner", "project", "m0")}
    connection.execute(
        text(
            "INSERT INTO project_report_jobs(id,user_id,project_id,source_manifest_job_id,request_key,source_digest,source_snapshot,version,status,attempt_count,pdf_status) VALUES (:id,:owner,:project,:m0,'key','digest','{}',1,'queued',0,'PDF_NOT_GENERATED')"
        ),
        ids,
    )
    with pytest.raises(IntegrityError, match="Frozen"):
        connection.execute(text("UPDATE project_report_jobs SET source_snapshot='changed'"))
    with pytest.raises(IntegrityError):
        connection.execute(
            text(
                "UPDATE project_report_jobs SET status='ready', html_file_record_id='abc', html_sha256='abc', html_size=NULL"
            )
        )
    connection.execute(text("UPDATE project_report_jobs SET status='validating'"))
    assert connection.scalar(text("SELECT status FROM project_report_jobs")) == "validating"
    connection.close()
    engine.dispose()


async def test_durable_create_gate_identity_and_drift(claim_env, monkeypatch):
    from cygnusx.application.schemas.project_report import CreateProjectReport
    from cygnusx.application.services import project_report_service as module
    from cygnusx.core.exceptions import DependencyUnavailableError
    from cygnusx.infrastructure.database.models.project_report import (
        ProjectReportJobModel,
        ProjectReportRequestModel,
    )

    env = claim_env
    _, request, selection = await prepare_env(env)
    ProjectReportJobModel.__table__.create(env.db.sync.bind, checkfirst=True)
    ProjectReportRequestModel.__table__.create(env.db.sync.bind, checkfirst=True)
    source = await selection.prepare(env.owner, env.project, request)
    create_request = CreateProjectReport(
        **request.model_dump(), prepare_digest=source.content_digest(), request_key=uuid4()
    )
    monkeypatch.setattr(module, "get_settings", lambda: env.settings)
    service = module.ProjectReportService(env.db)
    with pytest.raises(DependencyUnavailableError):
        await service.create(env.owner, env.project, create_request)
    env.settings.project_report_write_enabled = True
    job = await service.create(env.owner, env.project, create_request)
    assert job.status == "queued" and job.html_file_record_id is None
    assert (await service.create(env.owner, env.project, create_request)).id == job.id
    alias = create_request.model_copy(update={'request_key': uuid4()})
    assert (await service.create(env.owner, env.project, alias)).id == job.id
    changed = request.model_copy(update={'claims': ()})
    changed_source = await service.prepare(env.owner, env.project, changed)
    changed_request = CreateProjectReport(
        **changed.model_dump(), prepare_digest=changed_source.content_digest(), request_key=uuid4()
    )
    child = await service.create(env.owner, env.project, changed_request)
    assert child.parent_id == job.id and child.version == 2
    with pytest.raises(ConflictError):
        await service.create(env.owner, env.project, changed_request.model_copy(update={'request_key': alias.request_key}))
    assert (
        await service.status(env.owner, env.project, job.id)
    ).source_digest == source.content_digest()
    with pytest.raises(ConflictError):
        await service.create(
            env.owner, env.project, create_request.model_copy(update={"prepare_digest": "0" * 64})
        )
    with pytest.raises(NotFoundError):
        await service.status(env.other, env.project, job.id)


@pytest.mark.parametrize('pdf_failure', [False, True])
async def test_actual_html_publication_uses_shared_registry(claim_env, monkeypatch, pdf_failure):
    import hashlib

    from cygnusx.application.schemas.project_report import CreateProjectReport
    from cygnusx.application.services import project_report_publication as publication
    from cygnusx.application.services import project_report_service as module
    from cygnusx.application.services import report_service as reports
    from cygnusx.infrastructure.database.models.file import FileRecordModel
    from cygnusx.infrastructure.database.models.project_report import (
        ProjectReportJobModel,
        ProjectReportRequestModel,
    )
    from cygnusx.infrastructure.database.models.report import ReportFileModel
    from cygnusx.infrastructure.storage.backend import LocalStorageBackend

    env = claim_env
    _, request, selection = await prepare_env(env)
    if pdf_failure:
        from cygnusx.application.services import report_audit_pdf_renderer

        request = request.model_copy(update={'format': 'html_pdf'})
        env.settings.project_report_pdf_enabled = True

        def unavailable(*args, **kwargs):
            raise report_audit_pdf_renderer.AuditPdfRenderError('isolated failure')

        monkeypatch.setattr(report_audit_pdf_renderer, 'render_audit_pdf', unavailable)
    for model in (ProjectReportJobModel, ProjectReportRequestModel):
        model.__table__.create(env.db.sync.bind, checkfirst=True)
    source = await selection.prepare(env.owner, env.project, request)
    env.settings.project_report_write_enabled = True
    backend = LocalStorageBackend(env.factory)
    for mod in (module, publication, reports):
        monkeypatch.setattr(mod, "get_settings", lambda: env.settings)
    for mod in (publication, reports):
        monkeypatch.setattr(mod, "get_path_factory", lambda: env.factory)
    monkeypatch.setattr(publication, "get_storage_backend", lambda: backend)
    job = await module.ProjectReportService(env.db).create(
        env.owner,
        env.project,
        CreateProjectReport(
            **request.model_dump(), prepare_digest=source.content_digest(), request_key=uuid4()
        ),
    )
    await publication.run_project_report(env.db, job.id)
    assert job.status == "ready"
    content = (env.factory.data_root / job.archive_path).read_bytes()
    assert content.count(b"<section id=") == 14
    assert b"Content-Security-Policy" in content and b"<script" not in content
    assert hashlib.sha256(content).hexdigest() == job.html_sha256
    record = await env.db.get(FileRecordModel, job.html_file_record_id)
    assert record.checksum == job.html_sha256 and record.task_id is None
    files = env.db.sync.query(ReportFileModel).filter_by(project_report_job_id=job.id).all()
    assert len(files) == 1 and files[0].report_id is None
    assert files[0].file_record_id == record.id
    assert job.pdf_status == "PDF_NOT_GENERATED" and job.pdf_file_record_id is None
    await publication.run_project_report(env.db, job.id)
    assert env.db.sync.query(ReportFileModel).filter_by(project_report_job_id=job.id).count() == 1
    from cygnusx.core.exceptions import AuthorizationError
    from cygnusx.infrastructure import storage
    from cygnusx.infrastructure.database.models.project import ProjectModel

    monkeypatch.setattr(storage, "get_path_factory", lambda: env.factory)
    monkeypatch.setattr(storage, "get_storage_backend", lambda: backend)
    service = module.ProjectReportService(env.db)
    assert await service.download(env.owner, env.project, job.id) == content
    with pytest.raises(NotFoundError):
        await service.download(env.owner, env.project, job.id, "pdf")
    import io

    from cygnusx.application.schemas.project_delivery import CreateProjectExport, ExportSelectionV2
    from cygnusx.application.services.project_delivery_service import ProjectDeliveryService
    from cygnusx.domain.project_delivery_archive import verify_archive

    delivery_service = ProjectDeliveryService(env.db)
    m0 = await delivery_service.job(env.owner, env.project, request.source_manifest_job_id)
    original_digest = m0.manifest_digest
    original_zip = (env.factory.data_root / m0.archive_path).read_bytes()
    from cygnusx.application.services.bioreport_adapter import BioReportAdapter
    from cygnusx.application.services.download_service import DownloadService
    from cygnusx.application.services.task_service import TaskService

    def forbidden(*args, **kwargs):
        raise AssertionError('Export must never run analysis, download or scientific rendering')

    monkeypatch.setattr(TaskService, 'submit', forbidden)
    monkeypatch.setattr(DownloadService, 'submit', forbidden)
    monkeypatch.setattr(BioReportAdapter, 'render', forbidden)
    m1_selection = ExportSelectionV2(
        **m0.manifest["selection"],
        source_manifest_job_id=m0.id,
        project_report_job_ids=(job.id,),
    )
    m1 = await delivery_service.prepare(env.owner, env.project, m1_selection)
    assert m1.schema_version == "cygnusx.project_delivery.v2"
    assert m1.source_manifest_digest == original_digest
    assert any(f.source_id == files[0].id for f in m1.files)
    assert any("PDF_NOT_GENERATED" in gap for gap in m1.gaps)
    m1_job = await delivery_service.create(
        env.owner,
        env.project,
        CreateProjectExport(
            selection=m1_selection,
            manifest_digest=m1.content_digest(),
            request_key=uuid4(),
        ),
    )
    await run_project_export(env.db, m1_job.id)
    assert m1_job.status == "ready" and m1_job.id != m0.id
    zipped = (env.factory.data_root / m1_job.archive_path).read_bytes()
    document = verify_archive(io.BytesIO(zipped))
    assert await delivery_service.download(env.owner, env.project, m1_job.id) == zipped
    assert document["manifest_digest"] == m1.content_digest()
    assert m0.manifest_digest == original_digest
    assert (env.factory.data_root / m0.archive_path).read_bytes() == original_zip
    (env.factory.data_root / job.archive_path).write_bytes(b"tampered")
    with pytest.raises(ConflictError):
        await service.download(env.owner, env.project, job.id)
    project = await env.db.get(ProjectModel, env.project)
    project.status = "disabled"
    await env.db.commit()
    with pytest.raises(AuthorizationError):
        await service.download(env.owner, env.project, job.id)


async def test_report_rest_prepare_requires_jwt_for_create(claim_env, monkeypatch):
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from cygnusx.api import deps
    from cygnusx.api.v1.research_delivery import router
    from cygnusx.application.services import project_report_service
    from cygnusx.core.exceptions import CygnusXError
    from cygnusx.infrastructure.database.models.project_report import (
        ProjectReportJobModel,
        ProjectReportRequestModel,
    )

    env = claim_env
    _, request, _ = await prepare_env(env)
    for model in (ProjectReportJobModel, ProjectReportRequestModel):
        model.__table__.create(env.db.sync.bind, checkfirst=True)
    env.settings.project_report_write_enabled = True
    monkeypatch.setattr(project_report_service, 'get_settings', lambda: env.settings)
    app = FastAPI()
    app.include_router(router, prefix='/api/v1')

    async def database():
        yield env.db

    async def owner():
        return str(env.owner)

    async def authenticate(token):
        assert token == 'isolated-human'
        return str(env.owner)

    monkeypatch.setattr(deps, '_authenticate_jwt', authenticate)
    app.dependency_overrides[deps.get_db] = database
    app.dependency_overrides[deps.get_current_user_id] = owner

    @app.exception_handler(CygnusXError)
    async def failure(_request: Request, exc: CygnusXError):
        return JSONResponse({'code': exc.code}, status_code=exc.status_code)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://isolated.test') as client:
        base = f'/api/v1/projects/{env.project}/scientific-summary'
        prepared = await client.post(base + '/prepare', json=request.model_dump(mode='json'))
        assert prepared.status_code == 200
        assert env.db.sync.query(ProjectReportJobModel).count() == 0
        payload = {**request.model_dump(mode='json'), 'prepare_digest': prepared.json()['prepare_digest'], 'request_key': str(uuid4())}
        denied = await client.post(base, json=payload, headers={'X-API-Key': 'model'})
        assert denied.status_code == 401
        created = await client.post(base, json=payload, headers={'Authorization': 'Bearer isolated-human'})
        assert created.status_code == 200
        status = await client.get(base + '/' + created.json()['id'])
        assert status.json()['status'] == 'queued'
        assert status.json()['project_id'] == str(env.project)
        assert status.json()['html_file_record_id'] is None
        preview = await client.get(base + '/' + created.json()['id'] + '/preview')
        assert preview.status_code == 404
