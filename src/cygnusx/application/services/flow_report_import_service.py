"""Import offline Flow deliveries into an explicitly configured owner's report archive."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.services.flow_report_html import report_editions
from cygnusx.application.services.report_paths_contract import (
    REPORT_FILES_MAX_COUNT,
    REPORT_PATHS_MAX_BYTES,
    parse_report_paths,
    validate_relative_path,
)
from cygnusx.application.services.report_paths_registry import _role
from cygnusx.application.services.report_snapshot_manifest import (
    open_evidence_file,
    pinned_directory,
)
from cygnusx.core.config import get_settings
from cygnusx.domain.file.value_objects import FileSource
from cygnusx.infrastructure.database.models.report import ReportFileModel, ReportModel
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.storage import get_path_factory
from cygnusx.infrastructure.storage.file_registry import FileRegistry


def _stream_hash(
    stream: BinaryIO, maximum: int, destination: BinaryIO | None = None
) -> tuple[str, int]:
    before = os.fstat(stream.fileno())
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        if size > maximum:
            raise ValueError("Flow delivery exceeds import byte budget")
        digest.update(chunk)
        if destination:
            destination.write(chunk)
    after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) or size != after.st_size:
        raise ValueError("Flow delivery changed during import")
    return digest.hexdigest(), size


def _inventory(root: Path, maximum: int) -> tuple[dict[str, tuple[str, int]], str]:
    """Snapshot real bytes, rejecting links/special files and bounded by total bytes/count."""
    files: dict[str, tuple[str, int]] = {}
    total = 0
    stack = [root]
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                if entry.is_symlink():
                    raise ValueError("Flow delivery contains a symbolic link")
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                elif entry.is_file(follow_symlinks=False):
                    relative = validate_relative_path(path.relative_to(root).as_posix())
                    if relative.startswith(".cygnusx-"):
                        raise ValueError("Flow delivery uses reserved platform filenames")
                    if len(files) >= REPORT_FILES_MAX_COUNT:
                        raise ValueError("Flow delivery exceeds file count budget")
                    with open_evidence_file(path) as stream:
                        result = _stream_hash(stream, maximum - total)
                    total += result[1]
                    files[relative] = result
                else:
                    raise ValueError("Flow delivery contains a special file")
    digest = hashlib.sha256(json.dumps(sorted(files.items())).encode()).hexdigest()
    return files, digest


def _copy_snapshot(root: Path, archive: Path, files: dict[str, tuple[str, int]]) -> None:
    for relative, expected in files.items():
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with pinned_directory(target.parent) as directory_fd:
            fd = os.open(
                target.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
            with open_evidence_file(root / relative) as stream, os.fdopen(fd, "wb") as destination:
                observed = _stream_hash(stream, expected[1], destination)
        if observed != expected:
            raise ValueError(
                "Flow delivery changed after inventory; retry when publishing is complete"
            )


def _write_new(path: Path, content: bytes) -> None:
    with pinned_directory(path.parent) as directory_fd:
        fd = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        with os.fdopen(fd, "wb") as destination:
            destination.write(content)


class FlowReportImportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.factory = get_path_factory()

    async def scan(self) -> dict[str, int]:
        summary = {"imported": 0, "unchanged": 0, "failed": 0}
        if not self.settings.flow_report_import_enabled:
            return summary
        if not self.settings.flow_report_import_owner:
            raise ValueError("Flow report import requires an explicitly configured owner")
        owner = await self.db.scalar(
            select(UserModel).where(
                UserModel.username == self.settings.flow_report_import_owner,
                UserModel.status == "active",
            )
        )
        if owner is None:
            raise ValueError("Configured Flow report owner is not active")
        owner_id = owner.id
        root = (
            Path(self.settings.flow_report_import_root)
            if self.settings.flow_report_import_root
            else self.factory.data_root / "Flow_report"
        )
        if not root.is_dir():
            return summary
        if root.is_symlink():
            raise ValueError("Flow report root must not be a symbolic link")
        # A project is published as one immediate child containing report.paths.json.
        projects = await asyncio.to_thread(lambda: sorted(root.iterdir()))
        for project in projects:
            if (
                project.is_symlink()
                or not project.is_dir()
                or not (project / "report.paths.json").is_file()
            ):
                continue
            try:
                async with self.db.begin_nested():
                    changed = await self.import_project(owner_id, project, project.name)
                await self.db.commit()
                summary["imported" if changed else "unchanged"] += 1
            except Exception as exc:  # Keep other projects importable; no partial DB publication.
                await self.db.rollback()
                logger.warning(
                    "Flow report import failed project={}: {}", project.name, type(exc).__name__
                )
                summary["failed"] += 1
        return summary

    async def import_project(self, owner: UUID, root: Path, key: str) -> bool:
        files, digest = await asyncio.to_thread(
            _inventory, root, self.settings.flow_report_import_max_bytes
        )
        existing = await self.db.scalar(
            select(ReportModel).where(
                ReportModel.user_id == owner,
                ReportModel.external_source_key == key,
                ReportModel.external_source_digest == digest,
            )
        )
        if existing:
            return False
        with open_evidence_file(root / "report.paths.json") as stream:
            raw = stream.read(REPORT_PATHS_MAX_BYTES + 1)
        if len(raw) > REPORT_PATHS_MAX_BYTES:
            raise ValueError("Flow report metadata exceeds size budget")
        if hashlib.sha256(raw).hexdigest() != files["report.paths.json"][0]:
            raise ValueError("Flow report metadata changed after inventory")
        source: Any = json.loads(raw)
        if not isinstance(source, dict) or source.get("schema_version") not in {"2.0.0", "2.1.0"}:
            raise ValueError("Unsupported Flow report metadata")
        project = source.get("project", source.get("project_meta", {}))
        if not isinstance(project, dict):
            raise ValueError("Flow report project metadata must be an object")
        if project.get("user_id") not in {None, str(owner)}:
            raise ValueError("Flow report owner conflicts with configured owner")
        htmls = [path for path in files if "/" not in path and path.lower().endswith(".html")]
        declared = (source.get("platform") or {}).get("html_entry")
        entry = (
            validate_relative_path(declared) if declared else (htmls[0] if len(htmls) == 1 else "")
        )
        if entry not in files or not entry.endswith(".html"):
            raise ValueError("Flow delivery must identify exactly one primary HTML report")
        name = str(project.get("project_id") or key)[:120]
        previous = await self.db.scalar(
            select(ReportModel)
            .where(
                ReportModel.user_id == owner,
                ReportModel.external_source_key == key,
            )
            .order_by(ReportModel.version.desc())
            .limit(1)
        )
        archive = await asyncio.to_thread(
            self.factory.create_project_run_dir, str(owner), name, "flow-report-import"
        )
        owner_root = self.factory.user_root(str(owner)).absolute()
        if (
            owner_root.resolve() != owner_root
            or archive.resolve() != archive.absolute()
            or not archive.is_relative_to(owner_root)
        ):
            raise ValueError("Flow report archive is outside the owner storage scope")
        output = archive / "output"
        await asyncio.to_thread(_copy_snapshot, root, output, files)
        # Generated preview editions are separate from the immutable source HTML.
        html_bytes = await asyncio.to_thread((output / entry).read_bytes)
        editions = await asyncio.to_thread(
            report_editions, html_bytes, self.settings.flow_report_preview_max_bytes
        )
        for language, content in editions.items():
            await asyncio.to_thread(
                _write_new, output / f".cygnusx-preview-{language}.html", content
            )
        now = datetime.now(UTC)
        report_id = uuid4()
        index = [
            {
                "path": path,
                "role": _role(path),
                "description": path[:500],
                "format": Path(path).suffix.lower().lstrip(".") or "file",
            }
            for path in sorted(files)
        ]
        project_binding = {
            key: project.get(key)
            for key in ("client", "species", "genome_version", "pipeline_version", "analysis_date")
        }
        project_binding.update({"project_id": None, "user_id": str(owner)})
        flow = (source.get("report") or {}).get("type") or "flow"
        flow_id = {"rna-seq": "rna_seq", "atac-seq": "atac_seq"}.get(flow, str(flow))[:100]
        bound = {
            "schema_version": "2.1.0",
            "path_base": ".",
            "project": project_binding,
            "platform": {
                "report_id": str(report_id),
                "task_id": None,
                "user_id": str(owner),
                "source_kind": "external",
                "external_source_key": key,
                "html_entry": entry,
                "external_project_name": name,
            },
            "stats": source.get("stats", {}),
            "enrichment": source.get("enrichment", {}),
            "files": index,
        }
        projection = parse_report_paths(
            bound,
            report_id=str(report_id),
            task_id=None,
            owner_id=str(owner),
            external_source_key=key,
        )
        metadata = output / ".cygnusx-report.paths.json"
        encoded = json.dumps(bound, ensure_ascii=False).encode()
        if len(encoded) > REPORT_PATHS_MAX_BYTES:
            raise ValueError("Bound Flow report metadata exceeds size budget")
        await asyncio.to_thread(_write_new, metadata, encoded)
        report = ReportModel(
            id=report_id,
            task_id=None,
            user_id=owner,
            external_source_key=key,
            external_source_digest=digest,
            flow_id=flow_id,
            flow_name={"rna_seq": "RNA-seq", "atac_seq": "ATAC-seq"}.get(flow_id, flow_id),
            flow_version=str(project.get("pipeline_version") or "")[:20],
            flow_icon="📄",
            title=f"{name} 分析报告"[:200],
            description="外部 Flow 交付导入；未在平台执行分析",
            status="completed",
            sample_count=int(projection.stats.get("total_samples") or 0),
            duration=0,
            created_at=now,
            completed_at=now,
            report_kind="scientific",
            parent_id=previous.id if previous else None,
            version=previous.version + 1 if previous else 1,
            report_schema_version="2.1.0",
            report_paths_json_path=str(metadata),
            project_user_id=owner,
            project_client=project.get("client"),
            project_species=project.get("species"),
            genome_version=project.get("genome_version"),
            pipeline_version=project.get("pipeline_version"),
            analysis_date=project.get("analysis_date"),
            stats=projection.stats,
            enrichment_summary=projection.enrichment,
            files_index=index,
        )
        self.db.add(report)
        await self.db.flush()
        from cygnusx.application.services.file_service import ensure_directory_chain

        directory = output.relative_to(self.factory.user_root(str(owner))).as_posix()
        await ensure_directory_chain(self.db, owner, directory)
        registry = FileRegistry(self.db)
        for relative, (sha, size) in files.items():
            path = output / relative
            parent = path.parent.relative_to(self.factory.user_root(str(owner))).as_posix()
            await ensure_directory_chain(self.db, owner, parent)
            record = await registry.register(
                owner, path, source=FileSource.REPORT, directory=parent, checksum=sha
            )
            if relative == entry or path.suffix.lower() == ".pdf":
                self.db.add(
                    ReportFileModel(
                        report_id=report_id,
                        name=path.name,
                        type=path.suffix[1:],
                        size=size,
                        path=str(path),
                        is_primary=False,
                        sha256=sha,
                        file_record_id=record.id,
                    )
                )
        for language, content in editions.items():
            path = output / f".cygnusx-preview-{language}.html"
            sha = hashlib.sha256(content).hexdigest()
            record = await registry.register(
                owner, path, source=FileSource.REPORT, directory=directory, checksum=sha
            )
            self.db.add(
                ReportFileModel(
                    report_id=report_id,
                    name=f"{name}.{language}.html",
                    type="html",
                    size=len(content),
                    path=str(path),
                    is_primary=language == "zh",
                    sha256=sha,
                    file_record_id=record.id,
                )
            )
        await self.db.flush()
        return True
