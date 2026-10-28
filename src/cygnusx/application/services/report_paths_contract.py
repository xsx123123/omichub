"""Validation and safe relative-path access for BioReport report.paths.json."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from cygnusx.application.services.report_snapshot_manifest import open_evidence_file

REPORT_PATHS_MAX_BYTES = 2 * 1024 * 1024
REPORT_FILES_MAX_COUNT = 2000
REPORT_FILE_MAX_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class ReportPathsProjection:
    schema_version: str
    project: dict[str, Any]
    platform: dict[str, Any]
    stats: dict[str, Any]
    enrichment: dict[str, Any]
    files: tuple[dict[str, str], ...]
    degraded: bool


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _text(value: Any, label: str, *, required: bool = False, limit: int = 200) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} is invalid")
    return value.strip()


def validate_relative_path(raw_path: Any) -> str:
    """Accept only normalized POSIX paths relative to the report root."""
    if not isinstance(raw_path, str) or not raw_path or len(raw_path) > 1024:
        raise ValueError("artifact path is invalid")
    if "\\" in raw_path or "\x00" in raw_path:
        raise ValueError("artifact path is invalid")
    path = PurePosixPath(raw_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("artifact path escapes report root")
    normalized = path.as_posix()
    if normalized != raw_path or normalized.startswith("//"):
        raise ValueError("artifact path is not normalized")
    return normalized


def parse_report_paths(
    payload: Any,
    *,
    report_id: str,
    task_id: str | None,
    owner_id: str,
    external_source_key: str | None = None,
) -> ReportPathsProjection:
    data = _object(payload, "report.paths.json")
    version = data.get("schema_version")
    if version not in {"2.0.0", "2.1.0"}:
        raise ValueError("unsupported report.paths.json schema_version")

    if version == "2.1.0":
        project = _object(data.get("project"), "project")
        platform = _object(data.get("platform"), "platform")
        project_user = _text(project.get("user_id"), "project.user_id", required=True, limit=80)
        if project_user != owner_id:
            raise ValueError("project.user_id does not match report owner")
        project_id = _text(project.get("project_id"), "project.project_id", limit=120)
        if platform.get("report_id") != report_id or platform.get("task_id") != task_id:
            raise ValueError("platform report/task binding mismatch")
        if task_id is None and (
            not external_source_key or platform.get("source_kind") != "external"
            or platform.get("external_source_key") != external_source_key
        ):
            raise ValueError("external report source binding mismatch")
        if platform.get("user_id") not in {None, owner_id}:
            raise ValueError("platform.user_id does not match report owner")
        files_value = data.get("files")
        if not isinstance(files_value, list) or len(files_value) > REPORT_FILES_MAX_COUNT:
            raise ValueError("files index is invalid or too large")
        files: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in files_value:
            entry = _object(raw, "files entry")
            path = validate_relative_path(entry.get("path"))
            if path in seen:
                raise ValueError("files index contains duplicate paths")
            seen.add(path)
            files.append(
                {
                    "path": path,
                    "role": _text(entry.get("role"), "files.role", required=True, limit=80) or "",
                    "description": _text(
                        entry.get("description"), "files.description", required=True, limit=500
                    )
                    or "",
                    "format": _text(entry.get("format"), "files.format", required=True, limit=40)
                    or "",
                }
            )
        project = dict(project)
        project["project_id"] = project_id
        platform = dict(platform)
        stats = _object(data.get("stats", {}), "stats")
        enrichment = _object(data.get("enrichment", {}), "enrichment")
        return ReportPathsProjection(
            schema_version=version,
            project=project,
            platform=platform,
            stats=stats,
            enrichment=enrichment,
            files=tuple(files),
            degraded=False,
        )

    # Schema 2.0 predates platform ownership bindings. Its fields are advisory;
    # caller must supply the trusted Task/owner binding and mark the projection degraded.
    project = _object(data.get("project", data.get("project_meta", {})), "project")
    platform = _object(data.get("platform", {}), "platform")
    files_value = data.get("files", [])
    legacy_files: list[dict[str, str]] = []
    if isinstance(files_value, list):
        for raw in files_value[:REPORT_FILES_MAX_COUNT]:
            entry = _object(raw, "files entry")
            path = validate_relative_path(entry.get("path"))
            legacy_files.append(
                {
                    "path": path,
                    "role": str(entry.get("role") or "artifact")[:80],
                    "description": str(entry.get("description") or "Legacy report artifact")[:500],
                    "format": str(entry.get("format") or Path(path).suffix.lstrip("."))[:40],
                }
            )
    elif files_value not in (None, {}):
        raise ValueError("legacy files index is invalid")
    return ReportPathsProjection(
        schema_version=version,
        project=project,
        platform=platform,
        stats=_object(data.get("stats", {}), "stats"),
        enrichment=_object(data.get("enrichment", {}), "enrichment"),
        files=tuple(legacy_files),
        degraded=True,
    )


def read_local_report_file(root: Path, relative_path: str, *, max_bytes: int) -> bytes:
    """Read one indexed artifact through pinned, no-follow directory FDs."""
    normalized = validate_relative_path(relative_path)
    resolved_root = root.resolve(strict=True)
    target = resolved_root.joinpath(*PurePosixPath(normalized).parts)
    resolved_target = target.resolve(strict=True)
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("artifact path escapes report root") from exc
    with open_evidence_file(target) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise ValueError("artifact is not a regular file or exceeds size limit")
        content = stream.read(max_bytes + 1)
        after = os.fstat(stream.fileno())
    if len(content) > max_bytes or before.st_ino != after.st_ino or before.st_size != after.st_size:
        raise ValueError("artifact changed while reading or exceeds size limit")
    return content


def decode_report_paths(raw: bytes) -> Any:
    if len(raw) > REPORT_PATHS_MAX_BYTES:
        raise ValueError("report.paths.json exceeds size limit")
    return json.loads(raw.decode("utf-8"))
