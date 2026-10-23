"""Lifecycle persistence regressions on temporary SQLite and real retained files."""

import importlib.util
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from cygnusx.application.schemas.project import ProjectMetaDTO
from cygnusx.application.services import project_service as module
from cygnusx.application.services.project_overview_service import ProjectOverviewService
from cygnusx.application.services.project_service import ProjectService
from cygnusx.core.config import Settings
from cygnusx.core.exceptions import AuthorizationError, ConflictError, ValidationError
from cygnusx.infrastructure.config.storage_config import StorageConfig
from cygnusx.infrastructure.database.models.dataset import DatasetIngestionModel
from cygnusx.infrastructure.database.models.download_execution import (
    DownloadExecutionAdmissionModel,
    DownloadExecutionBudgetModel,
)
from cygnusx.infrastructure.database.models.file import DirectoryModel
from cygnusx.infrastructure.database.models.project import ProjectModel, ProjectTombstoneModel
from cygnusx.infrastructure.database.models.project_export import (
    ProjectExportJobModel,
    ProjectExportRequestModel,
)
from cygnusx.infrastructure.database.models.project_report import (
    ProjectReportJobModel,
    ProjectReportRequestModel,
)
from cygnusx.infrastructure.database.models.research_plan import ResearchPlanModel
from cygnusx.infrastructure.database.models.result_observation import ResultObservationModel
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.storage.path_factory import StoragePathFactory
from tests.unit.test_dataset_phase3 import registry as registry

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def lifecycle(registry: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    db, _, owner, other, project, *_ = registry
    # delete_project 预检查覆盖全部科研保留引用表，测试库需一并建齐
    for model in (
        ProjectTombstoneModel,
        DirectoryModel,
        DatasetIngestionModel,
        ResearchPlanModel,
        ResultObservationModel,
        DownloadExecutionBudgetModel,
        DownloadExecutionAdmissionModel,
        ProjectExportJobModel,
        ProjectExportRequestModel,
        ProjectReportJobModel,
        ProjectReportRequestModel,
    ):
        model.__table__.create(db.sync.bind)

    async def refresh(row: Any) -> None:
        db.sync.refresh(row)

    async def delete(row: Any) -> None:
        db.sync.delete(row)

    async def scalar(statement: Any) -> Any:
        return db.sync.scalar(statement)

    db.refresh = refresh
    db.delete = delete
    db.scalar = scalar
    db.add_all = db.sync.add_all
    factory = StoragePathFactory(StorageConfig(data_root=str(tmp_path), users_subdir="users"))
    monkeypatch.setattr(module, "get_path_factory", lambda: factory)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(_env_file=None))
    return ProjectService(db), db, owner, other, project, factory


async def test_delete_list_count_sync_never_resurrect_retained_run(lifecycle: Any) -> None:
    service, db, owner, _, _, factory = lifecycle
    created = await service.create_project(owner, "lifecycle-test")
    from uuid import UUID

    pid = UUID(created["id"])
    run = factory.project_dir(str(owner), created["slug"]) / "runs" / "legacy-run"
    run.mkdir()
    evidence = run / "README.md"
    evidence.write_text("retained evidence")
    await service.delete_project(owner, pid)
    for _ in range(3):
        assert created["id"] not in {p["id"] for p in await service.list_projects(owner)}
        assert await service.count_projects(owner) == 2
    synced = await service.sync_from_disk(owner)
    assert synced == {"created": 0, "skipped_deleted": 1}
    assert evidence.read_text() == "retained evidence"
    assert db.sync.get(ProjectTombstoneModel, pid).slug == created["slug"]
    with pytest.raises(ConflictError, match="身份"):
        await service.create_project(owner, "lifecycle-test")


async def test_read_is_pure_and_explicit_sync_adopts_only_missing_directory(lifecycle: Any) -> None:
    service, _, owner, _, project, factory = lifecycle
    root = factory.projects_dir(str(owner))
    (root / "genuine-legacy" / "runs" / "existing-run").mkdir(parents=True)
    (root / ".hidden").mkdir()
    (root / "linked").symlink_to(root / "genuine-legacy", target_is_directory=True)
    assert len(await service.list_projects(owner)) == 2
    assert await service.count_projects(owner) == 2
    assert await service.sync_from_disk(owner) == {"created": 1, "skipped_deleted": 0}
    assert await service.sync_from_disk(owner) == {"created": 0, "skipped_deleted": 0}
    assert await service.count_projects(owner) == 3
    assert (await service.get_project(owner, project))["slug"] == "owned"
    assert (root / "genuine-legacy" / "runs" / "existing-run").is_dir()


async def test_atomic_patch_preserves_slug_and_merges_nested_settings(lifecycle: Any) -> None:
    service, db, owner, _, project, _ = lifecycle
    await service.update_project_settings(
        owner,
        project,
        {
            "other": {"keep": True},
            "research_mode": {"enabled": False, "render_mode": "message_flow"},
            "array": [1, 2],
        },
    )
    result = await service.update_project(
        owner,
        project,
        {
            "name": " 新显示名 ",
            "description": "新描述",
            "status": "active",
            "settings": {"research_mode": {"enabled": True}, "array": [3]},
        },
    )
    assert result["name"] == "新显示名" and result["slug"] == "owned"
    assert result["description"] == "新描述" and result["status"] == "active"
    assert result["settings"] == {
        "other": {"keep": True},
        "research_mode": {"enabled": True, "render_mode": "message_flow"},
        "array": [3],
    }
    result = await service.update_project_settings(
        owner,
        project,
        {
            "other": None,
            "research_mode": {"render_mode": None},
        },
    )
    assert result["settings"] == {"research_mode": {"enabled": True}, "array": [3]}
    with pytest.raises(ValidationError):
        await service.update_project(
            owner, project, {"name": "must-not-commit", "status": "invalid"}
        )
    assert db.sync.get(ProjectModel, project).name == "新显示名"
    overview = await ProjectOverviewService(db)._load_project(owner, project)
    assert ProjectMetaDTO.model_validate(overview).settings == result["settings"]
    assert (await service.update_project(owner, project, {"settings": None}))["settings"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"name": None},
        {"name": "  "},
        {"description": None},
        {"description": "x" * 2001},
        {"settings": {"research_mode": True}},
        {"settings": {"research_mode": {"enabled": "yes"}}},
        {"slug": "changed"},
    ],
)
async def test_patch_validation(lifecycle: Any, changes: dict[str, Any]) -> None:
    service, _, owner, _, project, _ = lifecycle
    with pytest.raises(ValidationError):
        await service.update_project(owner, project, changes)


async def test_capability_owner_permissions_and_effective_export_dependency(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, db, owner, other, project, _ = lifecycle
    with pytest.raises(AuthorizationError):
        await service.capability_status(other, project)
    closed = await service.capability_status(owner, project)
    assert all(
        v == {"enabled": False, "allowed": False, "reason": "SERVICE_DISABLED"}
        for v in closed.model_dump().values()
    )
    settings = Settings(
        _env_file=None,
        research_plan_enabled=True,
        project_export_enabled=True,
        research_delivery_read_enabled=False,
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    db.sync.get(UserModel, owner).disabled_modules = ["tasks"]
    await db.commit()
    status = await service.capability_status(owner, project)
    assert status.research_plan.reason == "NO_PERMISSION"
    assert status.project_export.reason == "SERVICE_DISABLED"
    settings.research_delivery_read_enabled = True
    status = await service.capability_status(owner, project)
    assert status.research_delivery_read.allowed
    assert status.project_export.reason == "NO_PERMISSION"


async def test_migration_backfills_null_enforces_default_and_preserves_tombstones() -> None:
    spec = importlib.util.spec_from_file_location(
        "lifecycle_migration", "alembic/versions/project_lifecycle01.py"
    )
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE users (id UUID PRIMARY KEY)"))
        connection.execute(
            sa.text("CREATE TABLE projects (id UUID PRIMARY KEY, status VARCHAR(20))")
        )
        connection.execute(sa.text("INSERT INTO projects VALUES ('old', NULL)"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.scalar(sa.text("SELECT status FROM projects")) == "active"
            connection.execute(sa.text("INSERT INTO projects(id) VALUES ('new')"))
            assert (
                connection.scalar(sa.text("SELECT status FROM projects WHERE id='new'")) == "active"
            )
            owner, project = uuid4().hex, uuid4().hex
            connection.execute(sa.text("INSERT INTO users VALUES (:id)"), {"id": owner})
            connection.execute(
                sa.text(
                    "INSERT INTO project_tombstones(project_id,user_id,slug) VALUES (:p,:u,'deleted')"
                ),
                {"p": project, "u": owner},
            )
            with pytest.raises(RuntimeError, match="tombstones"):
                migration.downgrade()
            connection.execute(sa.text("DELETE FROM project_tombstones"))
            migration.downgrade()
    engine.dispose()
