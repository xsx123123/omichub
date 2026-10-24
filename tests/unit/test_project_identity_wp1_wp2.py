"""WP1/WP2 项目身份与删除保留回归（项目管理审计 F01/F02/F03，2026-10-24）。

覆盖：
- F01：已绑定项目的运行目录必须按稳定 slug 落盘（AgentTeams Case 场景，
  改名后显示名不得再决定目录）；
- F02：会话默认项目必须走统一身份预留（owner 锁 + tombstone 不复活），
  被删默认 slug 分配新 slug 而不是复用旧身份；
- F03：项目删除的科研 RESTRICT 引用必须转换为稳定 409（独立于功能开关），
  引用并发写入由数据库约束兜底、失败后完整回滚。

SQLite 内存库 + tmp_path 路径工厂。PRAGMA foreign_keys=ON 的用例只证明
FK 兜底路径可达；真实 PostgreSQL 并发、锁与 HTTP 行为仍需集成验收
（见 ARCHITECTURE_DESIGN/CygnusX_project_workspace_architecture.md §9）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from cygnusx.application.services import (
    agentteams_service as agentteams_module,
)
from cygnusx.application.services import (
    project_service as project_service_module,
)
from cygnusx.application.services.agentteams_service import AgentTeamsService
from cygnusx.application.services.chat.session_management import ChatSessionManagement
from cygnusx.application.services.project_service import ProjectService
from cygnusx.core.config import Settings
from cygnusx.core.exceptions import ConflictError, NotFoundError
from cygnusx.infrastructure.config.storage_config import StorageConfig
from cygnusx.infrastructure.database.models.agent_tool_invocation import AgentToolInvocationModel
from cygnusx.infrastructure.database.models.dataset import (
    DatasetIngestionModel,
    DatasetModel,
    DatasetVersionModel,
)
from cygnusx.infrastructure.database.models.download_execution import (
    DownloadExecutionAdmissionModel,
    DownloadExecutionBudgetModel,
)
from cygnusx.infrastructure.database.models.file import DirectoryModel, FileRecordModel
from cygnusx.infrastructure.database.models.project import (
    ProjectModel,
    ProjectTombstoneModel,
)
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
from cygnusx.infrastructure.database.models.user import UserModel, WorkspaceModel
from cygnusx.infrastructure.storage.path_factory import StoragePathFactory
from tests.unit.test_dataset_phase3 import OfflineDB

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def build_identity_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, fk: bool = True
) -> SimpleNamespace:
    """内存 SQLite + tmp_path 路径工厂；fk=True 时启用外键（模拟 PG RESTRICT 兜底）。"""
    engine = sa.create_engine("sqlite://")
    if fk:

        @sa.event.listens_for(engine, "connect")
        def _enable_fk(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _jsonb_to_json(element, compiler, **kwargs):  # noqa: ANN001, ANN202
        return "JSON"

    for model in (
        WorkspaceModel,
        UserModel,
        ProjectModel,
        ProjectTombstoneModel,
        DirectoryModel,
        DatasetModel,
        DatasetVersionModel,
        AgentToolInvocationModel,
        DatasetIngestionModel,
        ResearchPlanModel,
        ResultObservationModel,
        DownloadExecutionBudgetModel,
        DownloadExecutionAdmissionModel,
        FileRecordModel,
        ProjectExportJobModel,
        ProjectExportRequestModel,
        ProjectReportJobModel,
        ProjectReportRequestModel,
    ):
        model.__table__.create(engine)

    db = OfflineDB(engine)

    async def _refresh(row):  # noqa: ANN001, ANN202
        db.sync.refresh(row)

    async def _delete(row):  # noqa: ANN001, ANN202
        db.sync.delete(row)

    async def _scalar(statement):  # noqa: ANN001, ANN202
        return db.sync.scalar(statement)

    db.refresh = _refresh
    db.delete = _delete
    db.scalar = _scalar
    db.add_all = db.sync.add_all

    factory = StoragePathFactory(StorageConfig(data_root=str(tmp_path), users_subdir="users"))
    monkeypatch.setattr(project_service_module, "get_path_factory", lambda: factory)
    monkeypatch.setattr(project_service_module, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(agentteams_module, "get_path_factory", lambda: factory)

    owner, other = uuid4(), uuid4()
    for uid in (owner, other):
        db.add(
            UserModel(
                id=uid,
                username=str(uid),
                email=f"{uid}@invalid.test",
                hashed_password="unused",
                role="user",
                status="active",
                token_version=0,
            )
        )
    db.sync.commit()
    return SimpleNamespace(db=db, engine=engine, factory=factory, owner=owner, other=other)


class _SessionSvc(ChatSessionManagement):
    """最小可实例化的会话服务：DTO 转换原样返回。"""

    @staticmethod
    def _to_session_dto(session):  # noqa: ANN001, ANN202
        return session


# ----------------------------------------------------------------------
# F01：已绑定项目的运行目录按稳定 slug 落盘
# ----------------------------------------------------------------------


async def test_case_run_dir_keeps_stable_slug_after_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "原始项目")
    renamed = await service.update_project(env.owner, UUID(created["id"]), {"name": "改名后的项目"})
    assert renamed["slug"] == created["slug"] == "原始项目"

    agentteams = AgentTeamsService(Settings(_env_file=None))
    display_name, run_ref = await agentteams._prepare_case_run(
        requester_ref=str(env.owner),
        project_id=created["id"],
        project_name="改名后的项目",
        context_refs=[],
        db=env.db,
    )

    assert run_ref is not None and display_name == "改名后的项目"
    location = str(run_ref["location"])
    assert location.startswith(f"projects/{created['slug']}/runs/agentteams-case-")
    assert run_ref["meta"]["project_slug"] == created["slug"]
    assert (env.factory.data_root / "users" / str(env.owner) / location).is_dir()


async def test_case_run_dir_accepts_project_bound_without_display_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """调用方未传 project_name 时仍按解析出的项目 slug 落盘。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "Bound-Case")

    agentteams = AgentTeamsService(Settings(_env_file=None))
    _, run_ref = await agentteams._prepare_case_run(
        requester_ref=str(env.owner),
        project_id=created["id"],
        project_name=None,
        context_refs=[],
        db=env.db,
    )
    assert run_ref is not None
    assert str(run_ref["location"]).startswith(f"projects/{created['slug']}/runs/agentteams-case-")


# ----------------------------------------------------------------------
# F02：默认项目统一身份预留（tombstone 不复活）
# ----------------------------------------------------------------------


async def test_default_project_never_resurrects_retained_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    name = ChatSessionManagement.DEFAULT_PROJECT_NAME
    created = await service.create_project(env.owner, name)
    await service.delete_project(env.owner, UUID(created["id"]))
    assert env.db.sync.get(ProjectTombstoneModel, UUID(created["id"])) is not None

    svc = _SessionSvc()
    svc._db = env.db
    resolved = await svc._resolve_default_project_id(str(env.owner))

    assert resolved and resolved != created["id"]
    model = env.db.sync.get(ProjectModel, UUID(resolved))
    assert model is not None
    assert model.slug == f"{created['slug']}-2"
    assert model.user_id == env.owner
    # 旧身份保留：tombstone 仍在，旧 slug 未被新项目占用
    assert env.db.sync.get(ProjectTombstoneModel, UUID(created["id"])) is not None
    owned = sa.select(ProjectModel.slug).where(ProjectModel.user_id == env.owner)
    slugs = set(env.db.sync.execute(owned).scalars())
    assert created["slug"] not in slugs


async def test_default_project_reused_and_isolated_per_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = build_identity_env(tmp_path, monkeypatch)
    svc = _SessionSvc()
    svc._db = env.db

    first = await svc._resolve_default_project_id(str(env.owner))
    second = await svc._resolve_default_project_id(str(env.owner))
    assert first == second

    other = await svc._resolve_default_project_id(str(env.other))
    assert other != first
    assert env.db.sync.get(ProjectModel, UUID(other)).user_id == env.other


async def test_default_project_registers_directory_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """自动创建的默认项目同步登记 user_directories，与显式创建保持一致。"""
    env = build_identity_env(tmp_path, monkeypatch)
    svc = _SessionSvc()
    svc._db = env.db
    resolved = await svc._resolve_default_project_id(str(env.owner))
    model = env.db.sync.get(ProjectModel, UUID(resolved))
    assert model is not None
    path = f"projects/{model.slug}"
    row = env.db.sync.execute(
        sa.select(DirectoryModel).where(DirectoryModel.user_id == env.owner, DirectoryModel.path == path)
    ).scalar_one_or_none()
    assert row is not None


async def test_get_or_create_by_name_allocates_fresh_slug_when_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AgentTeams 按名称建单复用 tombstone 保留的 slug 时分配新身份，不抛冲突。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "case-x")
    await service.delete_project(env.owner, UUID(created["id"]))

    project = await service.get_or_create_project_by_name(env.owner, "case-x")
    assert project["id"] != created["id"]
    assert project["slug"] == "case-x-2"
    assert env.db.sync.get(ProjectTombstoneModel, UUID(created["id"])) is not None


# ----------------------------------------------------------------------
# F03：删除的科研引用保留契约
# ----------------------------------------------------------------------


def _seed_dataset(env: SimpleNamespace, project_id: UUID) -> None:
    env.db.add(DatasetModel(user_id=env.owner, project_id=project_id, name="d1"))


async def _seed_reference(kind: str, env: SimpleNamespace, project_id: UUID) -> None:
    now = datetime.now(UTC)
    if kind == "dataset":
        _seed_dataset(env, project_id)
    elif kind == "dataset_ingestion":
        env.db.add(
            DatasetIngestionModel(
                user_id=env.owner, project_id=project_id, request_key="rk", parameters_hash="h",
                normalized_request={},
            )
        )
    elif kind == "research_plan":
        env.db.add(
            ResearchPlanModel(
                user_id=env.owner, project_id=project_id, series_id=uuid4(), version=1,
                request_key="rk", draft={}, digest="d" * 64, status="DRAFT", steps=[],
                gaps=[],
            )
        )
    elif kind == "download_budget":
        env.db.add(
            DownloadExecutionBudgetModel(
                owner_id=env.owner, project_id=project_id, limit_bytes=100, reserved_bytes=0,
                disk_block_limit_bytes=100, disk_inodes_limit=10, status="ACTIVE",
                policy_revision="p1", expires_at=now + timedelta(days=1),
            )
        )
    elif kind == "result_observation":
        env.db.add(
            ResultObservationModel(
                user_id=env.owner, project_id=project_id, analysis_link_id=uuid4(),
                task_id=uuid4(), evidence_digest="e" * 64, payload={},
            )
        )
    elif kind == "download_admission":
        env.db.add(
            DownloadExecutionAdmissionModel(
                budget_id=uuid4(), ingestion_id=uuid4(), task_id=uuid4(), owner_id=env.owner,
                project_id=project_id, confirmation_id="c", request_digest="r" * 64, source="sra",
                protocol="https", policy_revision="p", environment_id="e", caller_id="u",
                caller_kind="user", tool_digest="t" * 64, source_digest="s" * 64,
                allowed_destinations=[], status="READY", expires_at=now + timedelta(days=1),
            )
        )
    else:
        # 导出/报告三链：request 与 report job 依赖前置行，按依赖顺序构造
        export_job = ProjectExportJobModel(
            user_id=env.owner, project_id=project_id, request_key="rk", manifest_digest="m" * 64,
            manifest={},
        )
        env.db.add(export_job)
        await env.db.flush()
        if kind == "export_job":
            return
        if kind == "export_request":
            env.db.add(
                ProjectExportRequestModel(
                    user_id=env.owner, project_id=project_id, request_key="rk-2",
                    job_id=export_job.id,
                )
            )
            return
        report_job = ProjectReportJobModel(
            user_id=env.owner, project_id=project_id, source_manifest_job_id=export_job.id,
            request_key="rk", source_digest="s" * 64, source_snapshot={}, version=1,
            status="queued",
        )
        env.db.add(report_job)
        await env.db.flush()
        if kind == "report_job":
            return
        if kind == "report_request":
            env.db.add(
                ProjectReportRequestModel(
                    user_id=env.owner, project_id=project_id, request_key="rk-2",
                    job_id=report_job.id,
                )
            )
            return
        raise AssertionError(f"unknown kind: {kind}")


_RETAINED_KINDS_DEFAULT_FK = (
    "dataset",
    "dataset_ingestion",
    "research_plan",
    "download_budget",
    "export_job",
    "export_request",
    "report_job",
    "report_request",
)
# 这两类引用自身还有指向 tasks / dataset_analysis_links 的 NOT NULL 外键，
# SQLite 内联 FK 建库成本高且本组只验证预检查投影，故关闭 FK pragma
_RETAINED_KINDS_NO_FK = ("result_observation", "download_admission")


@pytest.mark.parametrize("kind", _RETAINED_KINDS_DEFAULT_FK + _RETAINED_KINDS_NO_FK)
async def test_delete_blocked_by_retained_reference(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = build_identity_env(tmp_path, monkeypatch, fk=kind not in _RETAINED_KINDS_NO_FK)
    # 引用阻断必须独立于导出开关（默认关闭）
    assert Settings(_env_file=None).project_export_enabled is False
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, f"ref-{kind}")
    pid = UUID(created["id"])
    await _seed_reference(kind, env, pid)
    await env.db.commit()

    with pytest.raises(ConflictError) as excinfo:
        await service.delete_project(env.owner, pid)

    assert excinfo.value.code == "PROJECT_HAS_RETAINED_REFERENCES"
    assert str(excinfo.value.detail)
    # 预检查负责解释；阻断后不得留下部分提交（项目仍在、tombstone 未写）
    assert env.db.sync.get(ProjectModel, pid) is not None
    assert env.db.sync.execute(sa.select(ProjectTombstoneModel)).scalars().all() == []


async def test_delete_clean_project_writes_tombstone_and_keeps_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "clean-project")
    pid = UUID(created["id"])
    run = env.factory.project_dir(str(env.owner), created["slug"]) / "runs" / "legacy-run"
    run.mkdir(parents=True)
    (run / "README.md").write_text("retained evidence", encoding="utf-8")

    assert await service.delete_project(env.owner, pid) is True
    assert env.db.sync.get(ProjectModel, pid) is None
    tomb = env.db.sync.get(ProjectTombstoneModel, pid)
    assert tomb is not None and tomb.slug == created["slug"]
    assert (run / "README.md").read_text(encoding="utf-8") == "retained evidence"


async def test_delete_unexpected_integrity_error_converted_after_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """预检查与删除之间新增引用 → FK 兜底：回滚后重新解释为稳定 409。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "race-project")
    pid = UUID(created["id"])
    _seed_dataset(env, pid)
    await env.db.commit()

    real = service._retained_reference_counts
    calls = {"count": 0}

    async def flaky(*args: object, **kwargs: object) -> list[tuple[str, int]]:
        calls["count"] += 1
        if calls["count"] == 1:
            return []
        return await real(*args, **kwargs)

    monkeypatch.setattr(service, "_retained_reference_counts", flaky)

    with pytest.raises(ConflictError) as excinfo:
        await service.delete_project(env.owner, pid)

    assert excinfo.value.code == "PROJECT_HAS_RETAINED_REFERENCES"
    assert calls["count"] == 2
    assert env.db.sync.get(ProjectModel, pid) is not None
    assert env.db.sync.execute(sa.select(ProjectTombstoneModel)).scalars().all() == []


async def test_delete_foreign_project_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "mine-only")
    with pytest.raises(NotFoundError):
        await service.delete_project(env.other, UUID(created["id"]))


# ----------------------------------------------------------------------
# A 层补充验收（CygnusX_Project_Workspace_Test_Plan.md，2026-10-24）
# ----------------------------------------------------------------------


async def test_default_project_replacement_stable_across_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEF-04：替代默认项目建立后连续 5 次解析复用同一身份，不产生 -3/-4。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, ChatSessionManagement.DEFAULT_PROJECT_NAME)
    await service.delete_project(env.owner, UUID(created["id"]))

    svc = _SessionSvc()
    svc._db = env.db
    ids = [await svc._resolve_default_project_id(str(env.owner)) for _ in range(5)]

    assert len(set(ids)) == 1 and ids[0] != created["id"]
    model = env.db.sync.get(ProjectModel, UUID(ids[0]))
    assert model is not None and model.slug == f"{created['slug']}-2"


async def test_default_project_second_deletion_allocates_third_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEF-05：替代默认项目再次删除后不复用任何被保留 slug。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, ChatSessionManagement.DEFAULT_PROJECT_NAME)
    await service.delete_project(env.owner, UUID(created["id"]))

    svc = _SessionSvc()
    svc._db = env.db
    second = await svc._resolve_default_project_id(str(env.owner))
    await service.delete_project(env.owner, UUID(second))

    third = await svc._resolve_default_project_id(str(env.owner))
    model = env.db.sync.get(ProjectModel, UUID(third))
    assert model is not None and model.slug == f"{created['slug']}-3"
    tombs = {t.slug for t in env.db.sync.execute(sa.select(ProjectTombstoneModel)).scalars()}
    assert {created["slug"], f"{created['slug']}-2"} <= tombs


async def test_reserve_identity_does_not_commit_outer_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEF-09：身份预留仅 flush；外层事务回滚后不留行（helper 不得提前 commit）。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)

    model, created = await service.reserve_project_identity(
        env.owner, "外层事务项目", reuse_existing=True
    )
    assert created
    assert env.db.sync.get(ProjectModel, model.id) is not None
    await env.db.rollback()
    assert env.db.sync.get(ProjectModel, model.id) is None


async def test_default_project_skips_occupied_suffix_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEF-10：后缀 slug 已被存量项目占用时跳过，分配下一个可用值。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    name = ChatSessionManagement.DEFAULT_PROJECT_NAME
    base = await service.create_project(env.owner, name)
    await service.create_project(env.owner, f"{name}-2")
    await service.delete_project(env.owner, UUID(base["id"]))

    svc = _SessionSvc()
    svc._db = env.db
    resolved = await svc._resolve_default_project_id(str(env.owner))

    model = env.db.sync.get(ProjectModel, UUID(resolved))
    assert model is not None and model.slug == f"{base['slug']}-3"


async def test_renamed_default_project_still_reused_by_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """契约核对：默认项目按 slug 识别；改名（slug 不变）后仍复用，不另建默认项目。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, ChatSessionManagement.DEFAULT_PROJECT_NAME)
    await service.update_project(env.owner, UUID(created["id"]), {"name": "我的收纳项目"})

    svc = _SessionSvc()
    svc._db = env.db
    resolved = await svc._resolve_default_project_id(str(env.owner))

    assert resolved == created["id"]


async def test_delete_blocked_reports_multiple_reference_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEL-02：多类引用同时存在时完整返回阻断信息。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "multi-ref")
    pid = UUID(created["id"])
    _seed_dataset(env, pid)
    await _seed_reference("research_plan", env, pid)
    await env.db.commit()

    with pytest.raises(ConflictError) as excinfo:
        await service.delete_project(env.owner, pid)

    assert excinfo.value.code == "PROJECT_HAS_RETAINED_REFERENCES"
    assert "数据集 1" in str(excinfo.value.detail)
    assert "科研计划 1" in str(excinfo.value.detail)


async def test_double_delete_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEL-04：重复删除返回 404 语义，tombstone 唯一。"""
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "double-delete")
    pid = UUID(created["id"])

    assert await service.delete_project(env.owner, pid) is True
    with pytest.raises(NotFoundError):
        await service.delete_project(env.owner, pid)
    tombs = env.db.sync.execute(sa.select(ProjectTombstoneModel)).scalars().all()
    assert len(tombs) == 1 and tombs[0].slug == created["slug"]


async def test_unidentifiable_integrity_error_keeps_original_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEL-06：预检查清单之外的约束异常回滚后原样抛出，不伪装成科研引用冲突。"""
    from sqlalchemy.exc import IntegrityError

    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "unknown-ref")
    pid = UUID(created["id"])
    _seed_dataset(env, pid)
    await env.db.commit()

    async def always_empty(*args: object, **kwargs: object) -> list[tuple[str, int]]:
        return []

    monkeypatch.setattr(service, "_retained_reference_counts", always_empty)
    with pytest.raises(IntegrityError):
        await service.delete_project(env.owner, pid)

    assert env.db.sync.get(ProjectModel, pid) is not None
    assert env.db.sync.execute(sa.select(ProjectTombstoneModel)).scalars().all() == []


async def test_delete_mid_operation_failure_no_partial_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEL-07：删除中途注入失败，调用方回滚后无部分提交（项目在、无 tombstone）。"""

    class _ExplodingDirs:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_path(self, *args: object, **kwargs: object) -> object:
            return None

        async def save(self, *args: object, **kwargs: object) -> object:
            return None

        async def delete(self, *args: object, **kwargs: object) -> bool:
            raise RuntimeError("注入失败：目录删除前崩溃")

    env = build_identity_env(tmp_path, monkeypatch)
    monkeypatch.setattr(project_service_module, "DirectoryRepositoryImpl", _ExplodingDirs)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "midfail")
    pid = UUID(created["id"])

    with pytest.raises(RuntimeError):
        await service.delete_project(env.owner, pid)
    await env.db.rollback()

    assert env.db.sync.get(ProjectModel, pid) is not None
    assert env.db.sync.execute(sa.select(ProjectTombstoneModel)).scalars().all() == []


async def test_delete_blocked_with_export_flag_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """开关开启时科研引用同样阻断（与关闭态一致的错误码）。"""
    monkeypatch.setattr(
        project_service_module,
        "get_settings",
        lambda: Settings(_env_file=None, project_export_enabled=True),
    )
    env = build_identity_env(tmp_path, monkeypatch)
    service = ProjectService(env.db)
    created = await service.create_project(env.owner, "flag-on")
    pid = UUID(created["id"])
    await _seed_reference("export_job", env, pid)
    await env.db.commit()

    with pytest.raises(ConflictError) as excinfo:
        await service.delete_project(env.owner, pid)

    assert excinfo.value.code == "PROJECT_HAS_RETAINED_REFERENCES"


async def test_ensure_chat_archive_uses_bound_project_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ID-01（普通会话归档入口）：绑定项目的会话 run 目录按稳定 slug 落盘。"""
    from cygnusx.application.services import chat_archive_service
    from cygnusx.application.services.chat_archive_service import ensure_chat_archive

    factory = StoragePathFactory(StorageConfig(data_root=str(tmp_path), users_subdir="users"))
    monkeypatch.setattr(chat_archive_service, "get_path_factory", lambda: factory)

    uid = str(uuid4())
    project = SimpleNamespace(
        user_id=uid, name="改名后的标题", slug="chat-stable-slug",
        description="", customer="", created_at=None,
    )
    session = SimpleNamespace(
        session_id="sess-abc12345", user_id=uid, project_id=str(uuid4()),
        title="改名后的标题", sandbox_meta=None,
    )

    class _Db:
        async def scalar(self, _stmt: object) -> Any:
            return session

        async def get(self, model: object, _pk: object) -> Any:
            return project if model is ProjectModel else None

    ctx = await ensure_chat_archive(_Db(), uid, "sess-abc12345")

    assert ctx is not None
    assert ctx.run_dir.parent.parent.name == "chat-stable-slug"
    assert ctx.metadata["project_slug"] == "chat-stable-slug"
