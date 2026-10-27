"""Audit or backfill reports from report.paths.json under an explicit reports root.

The script is read-only unless --apply is passed and always requires an explicit
database URL. It writes success, failed, and manual JSON inventories to --output.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

from cygnusx.application.services.report_paths_contract import (
    REPORT_PATHS_MAX_BYTES,
    parse_report_paths,
    validate_relative_path,
)
from cygnusx.application.services.report_paths_registry import ReportPathsRegistryService
from cygnusx.infrastructure.database.models.report import ReportFileModel, ReportModel
from cygnusx.infrastructure.database.models.task import TaskModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _walk_report_files(root: Path) -> Iterator[Path]:
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False) and entry.name == "report.paths.json":
                        yield Path(entry.path)
        except OSError:
            continue


def _read_document(path: Path) -> dict[str, Any]:
    # Open with the same pinned FD discipline as report preview and Copilot reads.
    from cygnusx.application.services.report_snapshot_manifest import open_evidence_file

    with open_evidence_file(path) as stream:
        raw = stream.read(REPORT_PATHS_MAX_BYTES + 1)
    if len(raw) > REPORT_PATHS_MAX_BYTES:
        raise ValueError("report.paths.json exceeds size limit")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("report.paths.json must contain an object")
    return value


async def _match_report(
    db: AsyncSession, root: Path, payload: dict[str, Any]
) -> tuple[ReportModel | None, TaskModel | None, str]:
    raw_platform: Any = payload.get("platform")
    platform: dict[str, Any] = raw_platform if isinstance(raw_platform, dict) else {}
    raw_project: Any = payload.get("project") or payload.get("project_meta")
    project: dict[str, Any] = raw_project if isinstance(raw_project, dict) else {}
    owner_raw = project.get("user_id") or platform.get("user_id")
    owner_id: UUID | None = None
    if isinstance(owner_raw, str):
        try:
            owner_id = UUID(owner_raw)
        except ValueError:
            return None, None, "JSON owner user_id is not a UUID"

    report: ReportModel | None = None
    report_raw = platform.get("report_id")
    if isinstance(report_raw, str):
        try:
            report = await db.get(ReportModel, UUID(report_raw))
        except ValueError:
            report = None
        if report is not None and owner_id is not None and report.user_id != owner_id:
            return None, None, "report owner does not match JSON owner"
        if report is not None:
            owner_id = report.user_id

    task: TaskModel | None = None
    task_raw = platform.get("task_id") or project.get("task_id")
    if isinstance(task_raw, str):
        try:
            statement = select(TaskModel).where(TaskModel.id == UUID(task_raw))
            if owner_id is not None:
                statement = statement.where(TaskModel.user_id == owner_id)
            task = await db.scalar(statement)
        except ValueError:
            task = None
        if task is not None:
            owner_id = task.user_id

    if report is None:
        html_entry = platform.get("html_entry")
        if isinstance(html_entry, str):
            try:
                entry = validate_relative_path(html_entry)
                html_path = (root / entry).resolve(strict=True)
                html_path.relative_to(root.resolve(strict=True))
                report_file = await db.scalar(
                    select(ReportFileModel).where(ReportFileModel.path == str(html_path))
                )
                if report_file and report_file.report_id:
                    report = await db.get(ReportModel, report_file.report_id)
                    if report is not None:
                        if owner_id is not None and report.user_id != owner_id:
                            return None, None, "indexed HTML report owner does not match JSON owner"
                        owner_id = report.user_id
            except (OSError, ValueError):
                pass

    if task is None and report is not None:
        task = await db.scalar(
            select(TaskModel).where(
                TaskModel.id == report.task_id,
                TaskModel.user_id == owner_id,
            )
        )

    # Legacy reports without platform IDs are matched only through owner-scoped Task paths.
    if task is None and report is None:
        statement = select(TaskModel)
        if owner_id is not None:
            statement = statement.where(TaskModel.user_id == owner_id)
        tasks = await db.scalars(statement)
        root_real = root.resolve()
        matched: list[TaskModel] = []
        for candidate in tasks:
            if not candidate.work_dir:
                continue
            work = Path(candidate.work_dir)
            expected = {work, work.parent, work.parent / "data_deliver"}
            if candidate.result_path:
                expected.add(Path(candidate.result_path))
            if any(path.resolve() == root_real for path in expected):
                matched.append(candidate)
        if len(matched) == 1:
            task = matched[0]
            owner_id = task.user_id

    if report is None and task is not None:
        report = await db.scalar(
            select(ReportModel)
            .where(ReportModel.task_id == task.id, ReportModel.user_id == owner_id)
            .order_by(ReportModel.version.desc(), ReportModel.created_at.desc())
            .limit(1)
        )
    if report is None or task is None or owner_id is None:
        return None, None, "could not uniquely match JSON to an owner-scoped Report and Task"
    if report.user_id != owner_id or report.task_id != task.id or task.user_id != owner_id:
        return None, None, "Report/Task/JSON owner binding mismatch"
    return report, task, ""


async def _run(args: argparse.Namespace) -> int:
    reports_root = args.reports_root.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(args.database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    inventories: dict[str, list[dict[str, Any]]] = {
        "success": [],
        "failed": [],
        "manual": [],
    }
    try:
        async with sessions() as db:
            for paths_file in _walk_report_files(reports_root):
                root = paths_file.parent
                row: dict[str, Any] = {"json_path": str(paths_file)}
                try:
                    payload = _read_document(paths_file)
                    version = payload.get("schema_version")
                    if version not in {"2.0.0", "2.1.0"}:
                        raise ValueError("unsupported schema_version")
                    report, task, reason = await _match_report(db, root, payload)
                    if reason or report is None or task is None:
                        row["reason"] = reason
                        inventories["manual"].append(row)
                        continue
                    projection = parse_report_paths(
                        payload,
                        report_id=str(report.id),
                        task_id=str(task.id),
                        owner_id=str(report.user_id),
                    )
                    row.update({"report_id": str(report.id), "task_id": str(task.id), "schema_version": version})
                    if args.apply:
                        legacy_summary = payload if version == "2.0.0" else None
                        manifest_path = root / "result_manifest.json"
                        manifest: dict[str, Any] | None = None
                        if manifest_path.exists():
                            parsed = _read_document(manifest_path)
                            manifest = parsed
                        await ReportPathsRegistryService(db).register(
                            report,
                            task,
                            root,
                            legacy_summary=legacy_summary,
                            manifest=manifest,
                            promote_legacy=False,
                        )
                        await db.commit()
                        row["registered_schema_version"] = report.report_schema_version
                        if report.metadata_error:
                            row["reason"] = report.metadata_error
                            inventories["failed"].append(row)
                            continue
                    else:
                        row["file_count"] = len(projection.files)
                        row["validated"] = True
                    inventories["success"].append(row)
                except Exception as exc:  # noqa: BLE001 - retain per-report audit outcome
                    await db.rollback()
                    row["reason"] = f"{type(exc).__name__}: {str(exc)[:240]}"
                    inventories["failed"].append(row)
        for name, rows in inventories.items():
            (output / f"{name}.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    finally:
        await engine.dispose()
    print(json.dumps({key: len(value) for key, value in inventories.items()}, ensure_ascii=False))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--apply", action="store_true", help="persist validated registry metadata")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
