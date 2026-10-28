"""Actual SQLite registry and local files: external delivery identity, updates and isolation."""

from __future__ import annotations

import base64
import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cygnusx.application.services import flow_report_import_service as importer
from cygnusx.application.services import report_copilot_service, report_service
from cygnusx.application.services.flow_report_html import report_editions
from cygnusx.application.services.report_copilot_service import ReportCopilotService
from cygnusx.core.config import get_settings
from cygnusx.infrastructure.config.storage_config import StorageConfig
from cygnusx.infrastructure.database.models.file import DirectoryModel, FileRecordModel
from cygnusx.infrastructure.database.models.report import ReportFileModel, ReportModel
from cygnusx.infrastructure.database.models.task import TaskModel
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.storage import file_registry
from cygnusx.infrastructure.storage.backend import LocalStorageBackend
from cygnusx.infrastructure.storage.path_factory import StoragePathFactory

pytestmark = pytest.mark.integration


class SessionAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def scalar(self, query: Any) -> Any:
        return self.session.scalar(query)

    async def execute(self, query: Any) -> Any:
        return self.session.execute(query)

    async def get(self, model: Any, key: Any) -> Any:
        return self.session.get(model, key)

    def add(self, value: Any) -> None:
        self.session.add(value)

    async def flush(self) -> None:
        self.session.flush()

    async def refresh(self, value: Any) -> None:
        self.session.refresh(value)


@pytest.fixture
def archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    engine = create_engine("sqlite://")
    for model in (
        UserModel,
        ReportModel,
        ReportFileModel,
        FileRecordModel,
        DirectoryModel,
        TaskModel,
    ):
        model.__table__.create(engine)
    session = Session(engine, expire_on_commit=False)
    owner = UserModel(
        id=uuid4(),
        username="root",
        email="root@example.test",
        hashed_password="-",
        role="admin",
        status="active",
        disabled_modules=[],
        token_version=0,
    )
    session.add(owner)
    session.commit()
    factory = StoragePathFactory(
        StorageConfig(data_root=str(tmp_path / "storage"), users_subdir="users")
    )
    backend = LocalStorageBackend(path_factory=factory)
    for module in (importer, file_registry, report_service, report_copilot_service):
        monkeypatch.setattr(module, "get_path_factory", lambda: factory)
    monkeypatch.setattr(file_registry, "get_storage_backend", lambda: backend)
    monkeypatch.setattr(report_service, "get_storage_backend", lambda: backend)
    monkeypatch.setattr(get_settings(), "research_delivery_read_enabled", False)
    root = tmp_path / "delivery"
    root.mkdir()
    metadata = {
        "schema_version": "2.0.0",
        "project": {"project_id": "Tomato", "client": "jzhang"},
        "stats": {"total_samples": 15},
        "report": {"type": "rna-seq"},
    }
    (root / "report.paths.json").write_text(json.dumps(metadata))
    (root / "data").mkdir()
    (root / "data" / "DEG.csv").write_text("gene,padj\nA,0.01\n")
    (root / "report.html").write_text(
        "<html><head></head><body><h1>QC</h1><p>15 samples</p></body></html>"
    )
    db = cast(AsyncSession, SessionAdapter(session))
    yield {
        "service": importer.FlowReportImportService(db),
        "db": db,
        "session": session,
        "owner": owner,
        "root": root,
        "factory": factory,
    }
    session.close()
    engine.dispose()


async def test_import_is_taskless_idempotent_versioned_and_owner_scoped(
    archive: dict[str, Any],
) -> None:
    service, root, owner = archive["service"], archive["root"], archive["owner"]
    source_before = (root / "report.paths.json").read_bytes()
    assert await service.import_project(owner.id, root, "Tomato")
    report = archive["session"].scalar(select(ReportModel))
    assert report.task_id is None and report.external_source_key == "Tomato"
    assert report.sample_count == 15 and report.project_user_id == owner.id
    assert not archive["session"].scalars(select(TaskModel)).all()
    files = archive["session"].scalars(select(ReportFileModel)).all()
    assert any(file.is_primary for file in files)
    assert all(
        Path(file.path).is_relative_to(archive["factory"].user_root(str(owner.id)))
        for file in files
    )
    assert await service.import_project(owner.id, root, "Tomato") is False
    assert (root / "report.paths.json").read_bytes() == source_before
    copilot = ReportCopilotService(archive["db"], str(owner.id), "test")
    projection = await copilot._registered_projection(report, None)
    assert any(file["role"] == "deg_table" for file in projection["files"])
    query = await copilot._query_table(report, None, {"role": "deg_table"})
    assert query["rows"][0]["gene"] == "A"
    content = await report_service.ReportService(archive["db"]).preview_html(
        report.id, str(owner.id), strict=True
    )
    assert "15 samples" in content
    (root / "data" / "DEG.csv").write_text("gene,padj\nB,0.02\n")
    assert await service.import_project(owner.id, root, "Tomato")
    versions = archive["session"].scalars(select(ReportModel).order_by(ReportModel.version)).all()
    assert len(versions) == 2 and versions[1].parent_id == versions[0].id
    old_table = Path(versions[0].report_paths_json_path).parent / "data" / "DEG.csv"
    assert "A,0.01" in old_table.read_text()


async def test_import_rejects_links_and_conflicting_owner(archive: dict[str, Any]) -> None:
    root, service, owner = archive["root"], archive["service"], archive["owner"]
    (root / "link.csv").symlink_to(root / "data" / "DEG.csv")
    with pytest.raises(ValueError, match="symbolic link"):
        await service.import_project(owner.id, root, "Tomato")
    (root / "link.csv").unlink()
    metadata = json.loads((root / "report.paths.json").read_text())
    metadata["project"]["user_id"] = str(uuid4())
    (root / "report.paths.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="owner conflicts"):
        await service.import_project(owner.id, root, "Tomato")
    assert not archive["session"].scalars(select(ReportModel)).all()


def test_offline_editions_are_bounded_and_do_not_execute_loader() -> None:
    text = b"<html><head></head><body><h1>QC</h1></body></html>"
    encoded = base64.b64encode(gzip.compress(text)).decode()
    bundle = (
        "<script>throw new Error('must not execute')</script>"
        + "".join(
            f'<script id="edition-{language}" type="application/octet-stream">{encoded}</script>'
            for language in ("zh", "en")
        )
    ).encode()
    assert report_editions(bundle, 4096) == {"zh": text, "en": text}
    bomb = base64.b64encode(gzip.compress(b"x" * 10000)).decode()
    with pytest.raises(ValueError, match="exceeds preview budget"):
        report_editions(bundle.replace(encoded.encode(), bomb.encode()), 4096)
