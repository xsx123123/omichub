"""Materialize validated BioReport metadata into the owner-scoped report registry."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.services.report_archive import publish_archive, read_archive
from cygnusx.application.services.report_paths_contract import (
    REPORT_FILES_MAX_COUNT,
    decode_report_paths,
    parse_report_paths,
    validate_relative_path,
)
from cygnusx.core.exceptions import AuthorizationError
from cygnusx.infrastructure.database.models.report import ReportModel
from cygnusx.infrastructure.database.models.task import TaskModel
from cygnusx.infrastructure.storage import get_path_factory, get_storage_backend

_ROLE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deg_table", ("deg", "differential", "diff_gene")),
    ("enrichment_table", ("enrich", "go", "kegg", "pathway")),
    ("qc_stats", ("qc", "multiqc", "fastp", "mapping")),
)


def _role(path: str, category: str = "") -> str:
    text = f"{path} {category}".casefold()
    for role, tokens in _ROLE_RULES:
        if any(token in text for token in tokens):
            return role
    return "report_html" if path.lower().endswith((".html", ".htm")) else "artifact"


def _safe_date(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 32:
        return None
    return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None


class ReportPathsRegistryService:
    """Read a report paths document once, validate identity, and persist its projection."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.factory = get_path_factory()
        self.backend = get_storage_backend()

    async def register(
        self,
        report: ReportModel,
        task: TaskModel,
        report_root: Path,
        *,
        legacy_summary: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
        promote_legacy: bool = True,
    ) -> None:
        if report.user_id != task.user_id or report.task_id != task.id:
            raise AuthorizationError("Report/Task ownership mismatch")
        paths_path = report_root / "report.paths.json"
        try:
            owner_root = self.factory.user_root(str(report.user_id)).resolve()  # noqa: ASYNC240
            resolved_report_root = report_root.resolve()  # noqa: ASYNC240
            try:
                resolved_report_root.relative_to(owner_root)
            except ValueError as exc:
                raise AuthorizationError("Report root is outside the owner storage scope") from exc
            paths_rel = self.factory.relative_to_root(paths_path)
            if await self.backend.exists(paths_rel):
                raw = await read_archive(self.backend, self.factory, paths_rel, limit=2 * 1024 * 1024)
                payload = decode_report_paths(raw)
                projection = parse_report_paths(
                    payload,
                    report_id=str(report.id),
                    task_id=str(task.id),
                    owner_id=str(report.user_id),
                )
                # 2.0.0 did not carry the platform binding or role-indexed files. Fill those
                # fields from the already owner-checked Task/manifest and keep downgrade status.
                if projection.schema_version == "2.0.0":
                    payload = await self._promote_legacy_payload(
                        report, task, report_root, payload, legacy_summary, manifest
                    )
                    if promote_legacy:
                        payload["schema_version"] = "2.1.0"
                        await publish_archive(
                            self.backend,
                            self.factory,
                            paths_rel,
                            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                        )
                    projection = parse_report_paths(
                        payload,
                        report_id=str(report.id),
                        task_id=str(task.id),
                        owner_id=str(report.user_id),
                    )
                    if not promote_legacy:
                        projection = type(projection)(
                            schema_version="2.0.0",
                            project=projection.project,
                            platform=projection.platform,
                            stats=projection.stats,
                            enrichment=projection.enrichment,
                            files=projection.files,
                            degraded=True,
                        )
            else:
                payload = await self._new_payload(
                    report, task, report_root, legacy_summary or {}, manifest
                )
                projection = parse_report_paths(
                    payload,
                    report_id=str(report.id),
                    task_id=str(task.id),
                    owner_id=str(report.user_id),
                )
                await publish_archive(
                    self.backend,
                    self.factory,
                    paths_rel,
                    json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                )
            self._apply_projection(report, projection, paths_path)
            report.metadata_error = None
            if projection.stats.get("total_samples") is not None:
                report.sample_count = int(projection.stats["total_samples"])
            await self.db.flush()
        except Exception as exc:  # noqa: BLE001 - invalid metadata must become a visible failed report
            logger.warning("BioReport metadata registration failed report_id={}: {}", report.id, exc)
            report.status = "failed"
            report.completed_at = None
            report.metadata_error = f"report.paths.json validation failed: {type(exc).__name__}"[:240]
            await self.db.flush()

    async def _verified_project_id(self, task: TaskModel) -> str | None:
        """Only derive project identity from the existing owner-checked provenance service."""
        try:
            from cygnusx.application.services.research_provenance_service import (
                ResearchProvenanceService,
            )
            from cygnusx.infrastructure.database.models.dataset import (
                DatasetModel,
                DatasetVersionModel,
            )

            _, link = await ResearchProvenanceService(self.db).task_scope(task.user_id, task.id)
            if link is None:
                return None
            version = await self.db.get(DatasetVersionModel, link.version_id)
            dataset = await self.db.get(DatasetModel, version.dataset_id) if version else None
            return str(dataset.project_id) if dataset else None
        except Exception:  # noqa: BLE001 - report-scoped fallback is explicit
            return None

    async def _files_from_manifest(
        self, report_root: Path, manifest: dict[str, Any] | None
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        raw_entries = manifest.get("files", []) if isinstance(manifest, dict) else []
        if not isinstance(raw_entries, list):
            return rows
        for entry in raw_entries[:REPORT_FILES_MAX_COUNT]:
            if not isinstance(entry, dict):
                continue
            raw_path = entry.get("path")
            try:
                relative = validate_relative_path(raw_path)
            except ValueError:
                continue
            if str(entry.get("type", "")).lower() == "dir":
                continue
            target = (report_root / relative).resolve()
            try:
                target.relative_to(report_root.resolve())  # noqa: ASYNC240
            except ValueError:
                continue
            rel_data = self.factory.relative_to_root(target)
            try:
                if await self.backend.is_symlink(rel_data):
                    continue
                info = await self.backend.stat(rel_data)
            except Exception:  # noqa: BLE001
                continue
            if info is None or info.get("is_dir") or int(info.get("size") or 0) <= 0:
                continue
            suffix = target.suffix.lower().lstrip(".") or str(entry.get("type") or "file")[:40]
            rows.append(
                {
                    "path": relative,
                    "role": _role(relative, str(entry.get("category") or "")),
                    "description": str(entry.get("description") or entry.get("name") or relative)[:500],
                    "format": suffix,
                }
            )
        return rows

    async def _files_from_legacy_inputs(
        self, report_root: Path, input_files: Any
    ) -> list[dict[str, str]]:
        """Snapshot 2.0 input_files into a bounded index during registration, never at query time."""
        if not isinstance(input_files, dict):
            return []
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for key, raw_path in input_files.items():
            if not isinstance(key, str) or not isinstance(raw_path, str) or not raw_path:
                continue
            candidates: list[str] = []
            value = raw_path.strip()
            if value.startswith("/data/"):
                suffix = value[len("/data/") :]
                candidates.extend((f"report_data/data/{suffix}", suffix))
            else:
                try:
                    candidates.append(validate_relative_path(value))
                except ValueError:
                    continue
            for relative in candidates:
                try:
                    relative = validate_relative_path(relative)
                    absolute = (report_root / relative).resolve()
                    absolute.relative_to(report_root.resolve())  # noqa: ASYNC240
                    rel_data = self.factory.relative_to_root(absolute)
                    if await self.backend.is_symlink(rel_data):
                        continue
                    info = await self.backend.stat(rel_data)
                except (OSError, ValueError):
                    continue
                entries: list[dict[str, Any]]
                if info is not None and info.get("is_dir"):
                    try:
                        entries = [
                            entry
                            for entry in await self.backend.list(rel_data, recursive=True)
                            if entry.get("type") == "file"
                        ][: max(0, REPORT_FILES_MAX_COUNT - len(rows))]
                    except Exception:  # noqa: BLE001
                        continue
                elif info is not None:
                    entries = [{"path": rel_data, "type": "file", "size": info.get("size")}]
                else:
                    continue
                for entry in entries:
                    try:
                        full_path = self.factory.data_root / str(entry["path"])
                        indexed_path = full_path.relative_to(report_root.resolve()).as_posix()  # noqa: ASYNC240
                        indexed_path = validate_relative_path(indexed_path)
                    except (KeyError, ValueError):
                        continue
                    if indexed_path in seen or int(entry.get("size") or 0) <= 0:
                        continue
                    seen.add(indexed_path)
                    suffix = Path(indexed_path).suffix.lower().lstrip(".") or "file"
                    rows.append(
                        {
                            "path": indexed_path,
                            "role": _role(indexed_path, key),
                            "description": f"Legacy 2.0 report input: {key}",
                            "format": suffix,
                        }
                    )
                    if len(rows) >= REPORT_FILES_MAX_COUNT:
                        return rows
                if rows:
                    break
        return rows

    async def _new_payload(
        self,
        report: ReportModel,
        task: TaskModel,
        report_root: Path,
        summary: dict[str, Any],
        manifest: dict[str, Any] | None,
    ) -> dict[str, Any]:
        project_meta = summary.get("project_meta", summary.get("project", {}))
        project_meta = project_meta if isinstance(project_meta, dict) else {}
        stats = summary.get("stats", {})
        stats = stats if isinstance(stats, dict) else {}
        enrichment = summary.get("enrichment", {})
        enrichment = enrichment if isinstance(enrichment, dict) else {}
        files = await self._files_from_manifest(report_root, manifest)
        project_id = await self._verified_project_id(task)
        html_entry = None
        for item in files:
            if item["role"] == "report_html":
                html_entry = item["path"]
                break
        return {
            "schema_version": "2.1.0",
            "path_base": ".",
            "project": {
                "project_id": project_id,
                "user_id": str(task.user_id),
                "client": project_meta.get("client"),
                "species": project_meta.get("species"),
                "genome_version": project_meta.get("genome_version"),
                "pipeline_version": project_meta.get("pipeline_version") or task.flow_id,
                "analysis_date": _safe_date(project_meta.get("analysis_date")),
            },
            "platform": {
                "report_id": str(report.id),
                "task_id": str(task.id),
                "user_id": str(task.user_id),
                "project_id": project_id,
                "flow_type": task.flow_id,
                "flow_version": report.flow_version,
                "title": report.title,
                "status": report.status,
                "generated_at": report.completed_at.isoformat() if report.completed_at else None,
                "expire_at": None,
                "html_entry": html_entry,
            },
            "stats": stats,
            "enrichment": enrichment,
            "files": files,
        }

    async def _promote_legacy_payload(
        self,
        report: ReportModel,
        task: TaskModel,
        report_root: Path,
        old: dict[str, Any],
        summary: dict[str, Any] | None,
        manifest: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(summary or {})
        merged.update(old)
        new = await self._new_payload(report, task, report_root, merged, manifest)
        new["schema_version"] = "2.0.0"
        old_files = old.get("files")
        if isinstance(old_files, list) and old_files:
            # Keep the declared index after path normalization; malformed entries fail closed.
            new["files"] = [
                {
                    "path": validate_relative_path(entry.get("path")),
                    "role": str(entry.get("role") or "artifact")[:80],
                    "description": str(entry.get("description") or "Legacy report artifact")[:500],
                    "format": str(entry.get("format") or Path(str(entry["path"])).suffix.lstrip("."))[:40],
                }
                for entry in old_files[:REPORT_FILES_MAX_COUNT]
                if isinstance(entry, dict)
            ]
        elif not new["files"]:
            new["files"] = await self._files_from_legacy_inputs(
                report_root, old.get("input_files", merged.get("input_files"))
            )
        project = new["project"]
        legacy_project = old.get("project_meta", old.get("project", {}))
        if isinstance(legacy_project, dict):
            for key in ("client", "species", "genome_version", "pipeline_version", "analysis_date"):
                project[key] = legacy_project.get(key, project.get(key))
        platform = dict(new["platform"])
        new["platform"] = platform
        return new

    @staticmethod
    def _apply_projection(report: ReportModel, projection: Any, paths_path: Path) -> None:
        project = projection.project
        report.report_schema_version = projection.schema_version
        report.report_paths_json_path = str(paths_path)
        report.project_id = project.get("project_id")
        report.project_user_id = UUID(str(project.get("user_id")))
        report.project_client = project.get("client")
        report.project_species = project.get("species")
        report.genome_version = project.get("genome_version")
        report.pipeline_version = project.get("pipeline_version")
        report.analysis_date = _safe_date(project.get("analysis_date"))
        report.stats = projection.stats
        report.enrichment_summary = projection.enrichment
        report.files_index = list(projection.files)
        if (
            projection.degraded
            and report.description
            and "2.0.0 元数据降级" not in report.description
        ):
            report.description = f"{report.description} | 2.0.0 元数据降级"
