"""Read-only lineage, plus explicitly gated reconciliation of already existing outputs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.schemas.research_delivery import (
    ResearchArtifact,
    ResearchProvenance,
    ResearchReportLink,
)
from cygnusx.application.services.dataset_import_service import digest
from cygnusx.application.services.report_snapshot_manifest import safe_display_label
from cygnusx.application.services.research_execution_binding import check_inputs
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from cygnusx.domain.dataset.validation import ValidationLimits, checksum, open_owned_file
from cygnusx.domain.file.value_objects import FileSource
from cygnusx.infrastructure.database.models.dataset import (
    DatasetAnalysisLinkModel,
    DatasetModel,
    DatasetVersionModel,
)
from cygnusx.infrastructure.database.models.file import FileRecordModel
from cygnusx.infrastructure.database.models.project import ProjectModel
from cygnusx.infrastructure.database.models.report import (
    ReportFileModel,
    ReportGenerationJobModel,
    ReportModel,
    ReportSnapshotModel,
)
from cygnusx.infrastructure.database.models.result_observation import ResultObservationModel
from cygnusx.infrastructure.database.models.run import RunModel
from cygnusx.infrastructure.database.models.task import TaskModel
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.database.repositories.dataset_repository import DatasetRepository
from cygnusx.infrastructure.storage import get_path_factory
from cygnusx.infrastructure.storage.file_registry import FileRegistry


def require_research_read() -> None:
    if not get_settings().research_delivery_read_enabled:
        raise AuthorizationError("Research delivery is not enabled", code="FEATURE_DISABLED")


def require_research_write() -> None:
    from cygnusx.application.services.agent_tool_gateway import require_agent_write_gate

    require_agent_write_gate("analysis.submit")
    if not get_settings().research_delivery_write_enabled:
        raise AuthorizationError("Research delivery write gate blocked", code="WRITE_GATE_BLOCKED")


def relative_file(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or len(value) > 1024
        or path.is_absolute()
        or any(part in {"..", "."} for part in value.split("/"))
        or "\\" in value
        or ":" in value
        or any(ord(c) < 32 for c in value)
    ):
        raise ValidationError("Invalid manifest path", code="PATH_ESCAPE")
    return path.as_posix()


def observation_payload(graph: ResearchProvenance) -> dict[str, Any]:
    payload = graph.model_dump(
        mode="json",
        exclude={
            "result_observation_id",
            "reports",
            "report_jobs",
            "delivery_state",
            "evidence_state",
        },
    )
    payload["gaps"] = sorted(
        set(graph.gaps) - {"RESULT_OBSERVATION_MISSING", "RESULT_OBSERVATION_STALE"}
    )
    return payload


class ResearchProvenanceService:
    _project_truncated: bool
    _project_links_remaining: int

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = DatasetRepository(db)

    async def task_scope(
        self, owner: UUID, task_id: UUID
    ) -> tuple[TaskModel, DatasetAnalysisLinkModel | None]:
        user = await self.db.get(UserModel, owner)
        if not user or user.status != "active":
            raise NotFoundError("User unavailable")
        await self.repo.require_module(owner, "reports")
        task = (
            await self.db.execute(
                select(TaskModel).where(TaskModel.id == task_id, TaskModel.user_id == owner)
            )
        ).scalar_one_or_none()
        if task is None:
            raise NotFoundError("Task not found")
        link = (
            await self.db.execute(
                select(DatasetAnalysisLinkModel).where(DatasetAnalysisLinkModel.task_id == task.id)
            )
        ).scalar_one_or_none()
        if link:
            version = await self.db.get(DatasetVersionModel, link.version_id)
            if not version:
                raise ConflictError("Dataset version missing")
            dataset = await self.db.get(DatasetModel, version.dataset_id)
            if not dataset:
                raise ConflictError("Dataset missing")
            await self.repo.version(owner, dataset.project_id, dataset.id, version.id)
            if link.normalized_request.get("owner_id") != str(owner) or link.normalized_request.get(
                "project_id"
            ) != str(dataset.project_id):
                raise ConflictError("Execution scope mismatch")
        return task, link

    async def dataset(
        self, owner: UUID, project: UUID, dataset: UUID, version: UUID
    ) -> dict[str, Any]:
        row = await self.repo.version(owner, project, dataset, version)
        links = (
            (
                await self.db.execute(
                    select(DatasetAnalysisLinkModel)
                    .where(DatasetAnalysisLinkModel.version_id == row.id)
                    .order_by(DatasetAnalysisLinkModel.created_at)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        limit = getattr(self, "_project_links_remaining", 100)
        selected_links = links[:limit]
        if hasattr(self, "_project_links_remaining"):
            self._project_links_remaining -= len(selected_links)
            self._project_truncated = self._project_truncated or len(links) > len(selected_links)
        return {
            "project_id": str(project),
            "dataset_id": str(dataset),
            "dataset_version_id": str(version),
            "handoff_hash": row.handoff.get("manifest_hash") if row.handoff else None,
            "analyses": [
                await self._project_analysis(owner, link.task_id)
                if link.task_id
                else {
                    "analysis_link_id": str(link.id),
                    "task_id": None,
                    "compute_state": link.state,
                    "delivery_state": "BLOCKED",
                    "gaps": ["TASK_NOT_CREATED"],
                }
                for link in selected_links
            ],
            "gaps": [] if row.handoff else ["HANDOFF_NOT_FROZEN"],
        }

    async def _project_analysis(self, owner: UUID, task_id: UUID) -> dict[str, Any]:
        try:
            return (await self.task(owner, task_id)).model_dump(mode="json")
        except (NotFoundError, ConflictError):
            if not getattr(self, "_tolerate_unavailable", False):
                raise
            return {
                "task_id": None,
                "state": "UNAVAILABLE",
                "association_status": "UNAVAILABLE",
                "gaps": ["LINKED_TASK_UNAVAILABLE"],
            }

    async def project(
        self, owner: UUID, project: UUID, *, tolerate_unavailable: bool = False
    ) -> dict[str, Any]:
        self._tolerate_unavailable = tolerate_unavailable
        await self.repo.require_module(owner, "reports")
        await self.repo.project(owner, project)
        self._project_links_remaining = 20
        self._project_truncated = False
        datasets = await self.repo.list(owner, project)
        chains = []
        for dataset in datasets[:20]:
            versions = (
                (
                    await self.db.execute(
                        select(DatasetVersionModel)
                        .where(DatasetVersionModel.dataset_id == dataset.id)
                        .order_by(DatasetVersionModel.number.desc())
                        .limit(5)
                    )
                )
                .scalars()
                .all()
            )
            self._project_truncated = self._project_truncated or len(versions) >= 5
            for version in versions:
                chains.append(await self.dataset(owner, project, dataset.id, version.id))
        return {
            "schema_version": "cygnusx.research_delivery.v1",
            "project_id": str(project),
            "datasets": chains,
            "runtime_admission": "BLOCKED",
            "truncated": self._project_truncated
            or len(datasets) >= 20
            or any(len(c["analyses"]) >= 100 for c in chains),
        }

    async def task(
        self, owner: UUID, task_id: UUID, *, include_reports: bool = True
    ) -> ResearchProvenance:
        if not hasattr(self, "_capture_deadline"):
            self._capture_deadline = (
                time.monotonic() + get_settings().research_capture_timeout_seconds
            )
            self._captured_bytes = 0
        task, link = await self.task_scope(owner, task_id)
        graph = ResearchProvenance(
            owner_id=owner,
            task_id=task.id,
            compute_state=task.status,
            started_at=task.started_at.isoformat() if task.started_at else None,
            finished_at=task.finished_at.isoformat() if task.finished_at else None,
        )
        graph.gaps = ["RUNTIME_IMAGE_NOT_OBSERVED", "WORKFLOW_RELEASE_NOT_ATTESTED"]
        from cygnusx.application.services.execution_evidence_service import evidence_projection

        execution_evidence = evidence_projection(task)
        if execution_evidence is not None:
            graph.runtime["execution_evidence"] = execution_evidence
        runs = (
            (
                await self.db.execute(
                    select(RunModel).where(
                        RunModel.task_id == task.id,
                        RunModel.user_id == owner,
                        RunModel.flow_id == task.flow_id,
                        RunModel.confirmed_at.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(runs) > 1:
            raise ConflictError("Ambiguous Run")
        graph.run_id = runs[0].id if runs else None
        if not runs:
            graph.gaps.append("RUN_NOT_RECORDED")
        if not link:
            graph.gaps += ["DATASET_LINEAGE_UNKNOWN", "EXECUTION_BINDING_UNKNOWN"]
            graph.flow = {
                "id": task.flow_id,
                "version": None,
                "config_sha256": None,
                "status": "UNKNOWN",
            }
            graph.delivery_state = "BLOCKED"
        else:
            version = await self.db.get(DatasetVersionModel, link.version_id)
            assert version is not None
            dataset = await self.db.get(DatasetModel, version.dataset_id)
            assert dataset is not None
            graph.project_id, graph.dataset_id, graph.dataset_version_id = (
                dataset.project_id,
                dataset.id,
                version.id,
            )
            graph.analysis_link_id, graph.handoff_hash = link.id, link.handoff_hash
            binding = link.execution_binding or {}
            graph.flow = {
                "id": link.flow_id,
                "version": binding.get("flow_version"),
                "config_sha256": binding.get("flow_config_sha256"),
                "status": "PREPARE_CAPTURE" if binding else "UNKNOWN",
            }
            graph.parameters_sha256 = binding.get("parameters_sha256")
            parameters = link.normalized_request.get("request", {}).get("parameters", {})
            for key in (
                "species",
                "genome",
                "reference",
                "treatment",
                "alpha",
                "fit_type",
                "strandedness",
                "aligner",
            ):
                value = parameters.get(key)
                if (
                    isinstance(value, (bool, int, float))
                    or isinstance(value, str)
                    and safe_display_label(value)
                ):
                    graph.analysis_parameters[key] = value
            design = parameters.get("design")
            if (
                isinstance(design, str)
                and len(design) <= 80
                and re.fullmatch(r"~\s*(?:group|batch)(?:\s*\+\s*(?:group|batch))*", design)
            ):
                graph.analysis_parameters["design"] = design
            graph.runtime = {
                **graph.runtime,
                "image_digest": None,
                "software_versions": None,
                "observation": "NOT_OBSERVED",
            }
            handoff = version.handoff or {}
            # Explicit whitelist: no raw metadata, prompts, parameters, tokens or server paths.
            graph.source = [
                {
                    key: source.get(key)
                    for key in ("repository", "accession", "parent_accession", "access_status")
                }
                for source in handoff.get("source", [])
            ]
            for source in handoff.get("source", []):
                evidence = source.get("evidence", {})
                if isinstance(evidence, dict):
                    safe = {
                        k: evidence.get(k)
                        for k in ("response_sha256", "retrieved_at", "api_version")
                    }
                    url = evidence.get("url") or source.get("source_url")
                    if isinstance(url, str) and len(url) <= 2048:
                        parsed = urlsplit(url)
                        if (
                            parsed.scheme == "https"
                            and parsed.hostname in {"www.ncbi.nlm.nih.gov", "www.ebi.ac.uk"}
                            and not parsed.username
                            and not parsed.password
                        ):
                            safe["url"] = urlunsplit(
                                (
                                    "https",
                                    parsed.hostname,
                                    parsed.path,
                                    urlencode(
                                        [
                                            (k, v)
                                            for k, v in parse_qsl(parsed.query)
                                            if k in {"acc", "db", "id", "accession"}
                                        ]
                                    ),
                                    "",
                                )
                            )
                    graph.source.append({"evidence": safe})
            if not any(
                source.get("repository") and source.get("accession") for source in graph.source
            ):
                graph.gaps.append("SOURCE_EVIDENCE_UNKNOWN")
            graph.samples = [
                {
                    "sample_id": s.get("sample_id"),
                    "sample_key": safe_display_label(s.get("sample_key")),
                    "group": safe_display_label(s.get("user_annotation", {}).get("group")),
                    "mapping_status": s.get("mapping_status"),
                    "reviewed_by": s.get("user_annotation", {}).get("reviewed_by"),
                    "group_confirmed": s.get("user_annotation", {}).get("group_confirmed", False),
                }
                for s in handoff.get("samples", [])
            ]
            graph.inputs = [
                ResearchArtifact(
                    file_record_id=UUID(a["file_record_id"]),
                    logical_name="input/" + str(i + 1),
                    size=a.get("size"),
                    sha256=a.get("sha256"),
                    integrity="UNKNOWN",
                )
                for i, a in enumerate(handoff.get("assets", []))
            ]
            try:
                await check_inputs(self.db, owner, link, require_worker=False)
                graph.input_integrity = "VERIFIED"
                for asset in graph.inputs:
                    asset.integrity = "VERIFIED"
            except (ValidationError, ConflictError, OSError):
                graph.input_integrity = "FAILED"
                graph.gaps.append("INPUT_INTEGRITY_FAILED")
            if not binding:
                graph.gaps.append("EXECUTION_BINDING_UNKNOWN")
            await self._manifest(graph, task, link)
            observation = (
                await self.db.execute(
                    select(ResultObservationModel)
                    .where(
                        ResultObservationModel.task_id == task.id,
                        ResultObservationModel.user_id == owner,
                        ResultObservationModel.evidence_digest
                        == digest(observation_payload(graph)),
                    )
                    .order_by(
                        ResultObservationModel.created_at.desc(), ResultObservationModel.id.desc()
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if observation:
                graph.result_observation_id = observation.id
            else:
                graph.gaps.append("RESULT_OBSERVATION_MISSING")
            if include_reports:
                await self._reports(graph)
            complete = (
                graph.input_integrity == "VERIFIED"
                and graph.result_integrity == "VERIFIED"
                and not (set(graph.gaps) - {"RUN_NOT_RECORDED"})
                and task.status in {"success", "completed"}
            )
            graph.evidence_state = "VERIFIED" if complete else "PARTIAL"
            kinds = {r.kind for r in graph.reports if r.integrity == "VERIFIED"}
            graph.delivery_state = (
                "READY"
                if complete and {"scientific", "reproducibility"}.issubset(kinds)
                else "PARTIAL"
                if graph.artifacts or graph.reports
                else "BLOCKED"
            )
        if not link and include_reports:
            await self._reports(graph)
        graph.gaps = sorted(set(graph.gaps))
        return graph

    async def _manifest(
        self, graph: ResearchProvenance, task: TaskModel, link: DatasetAnalysisLinkModel
    ) -> None:
        settings = get_settings()
        factory = get_path_factory()
        root = factory.user_root(str(task.user_id))
        work = Path(task.work_dir)  # noqa: ASYNC240
        project = await self.db.get(ProjectModel, graph.project_id) if graph.project_id else None
        project_root = root / "projects" / project.slug if project else root
        if (
            not task.work_dir
            or not work.is_absolute()
            or not work.resolve().is_relative_to(project_root.resolve())  # noqa: ASYNC240
        ):
            graph.result_integrity = "FAILED"
            graph.gaps.append("RESULT_ROOT_INVALID")
            return
        candidates = [Path(task.result_path)] if task.result_path else []
        candidates += (
            [Path(task.parameters["data_deliver"])]
            if isinstance(task.parameters.get("data_deliver"), str)
            and task.parameters["data_deliver"]
            else []
        )
        candidates += [work / "results", work.parent / "output", work]
        found = None
        for directory in candidates:
            if (
                not directory.resolve().is_relative_to(root.resolve())
                or directory.resolve() == root.resolve()
            ):
                graph.result_integrity = "FAILED"
                graph.gaps.append("RESULT_ROOT_INVALID")
                return
            for name in ("result_manifest.delivery.json", "result_manifest.json"):
                if (directory / name).exists():
                    found = directory / name
                    break
            if found:
                break
        if found is None:
            graph.result_integrity = "MISSING"
            graph.gaps.append("RESULT_MANIFEST_MISSING")
            return
        try:
            with open_owned_file(found, root) as stream:
                content = stream.read(settings.research_manifest_max_bytes + 1)
            if len(content) > settings.research_manifest_max_bytes:
                raise ValidationError("Manifest budget")
            raw = json.loads(content)
            if not isinstance(raw, dict):
                raise ValidationError("Manifest object required")
            graph.manifest_sha256 = hashlib.sha256(content).hexdigest()
            platform = raw.get("platform", {})
            if not isinstance(platform, dict):
                raise ValidationError("Invalid platform block")
            for key, expected in {
                "task_id": str(task.id),
                "user_id": str(task.user_id),
                "flow_id": task.flow_id,
            }.items():
                if platform.get(key) is None:
                    graph.gaps.append("MANIFEST_IDENTITY_UNKNOWN")
                elif platform[key] != expected:
                    raise ConflictError("Manifest identity mismatch")
            binding = link.execution_binding or {}
            lineage = raw.get("cygnusx", {})
            if not isinstance(lineage, dict):
                raise ValidationError("Invalid lineage block")
            expected_lineage = {
                "dataset_version_id": str(link.version_id),
                "handoff_hash": link.handoff_hash,
                "parameters_sha256": binding.get("parameters_sha256"),
                "flow_config_sha256": binding.get("flow_config_sha256"),
                "flow_version": binding.get("flow_version"),
            }
            for key, value in expected_lineage.items():
                if value is None or lineage.get(key) is None:
                    graph.gaps.append("MANIFEST_INPUT_BINDING_UNKNOWN")
                elif lineage[key] != value:
                    raise ConflictError("Manifest input binding mismatch")
            declared = raw.get("files")
            if declared is None and isinstance(raw.get("outputs"), list):
                declared = [{"path": name} for name in raw["outputs"]]
                graph.gaps.append("MANIFEST_INPUT_BINDING_UNKNOWN")
            if (
                not isinstance(declared, list)
                or not declared
                or len(declared) > settings.research_artifact_max_files
            ):
                raise ValidationError("Manifest file budget")
            seen = set()
            total = 0
            deadline = self._capture_deadline
            for index, item in enumerate(declared):
                if not isinstance(item, dict):
                    raise ValidationError("Invalid file declaration")
                name = relative_file(item["path"])
                if name in seen:
                    raise ValidationError("Duplicate artifact")
                seen.add(name)
                asset = ResearchArtifact(
                    logical_name=name
                    if name
                    in {
                        "deg.tsv",
                        "sample_qc.tsv",
                        "qc.pdf",
                        "session_info.txt",
                        "index.html",
                        "report.html",
                    }
                    else "artifact/" + str(index + 1),
                    category=item.get("category", "other")
                    if item.get("category") in {"report", "qc", "expression", "deg", "log", "other"}
                    else "other",
                    declared_sha256=item.get("sha256"),
                )
                path = found.parent / name
                try:
                    with open_owned_file(path, root) as stream:
                        before = os.fstat(stream.fileno())
                        actual, size = checksum(
                            stream,
                            ValidationLimits(
                                max_bytes=settings.research_artifact_max_bytes
                                - self._captured_bytes
                            ),
                        )
                        md5 = hashlib.md5(usedforsecurity=False)
                        while chunk := stream.read(1024 * 1024):
                            md5.update(chunk)
                        after = os.fstat(stream.fileno())
                    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ):
                        raise ConflictError("Artifact changed during capture")
                    total += size
                    self._captured_bytes += size
                    if time.monotonic() > deadline:
                        raise ValidationError("Capture deadline")
                    asset.sha256, asset.size = actual, size
                    declared_size = item.get("size_bytes", item.get("size"))
                    if (
                        (item.get("sha256") and item["sha256"] != actual)
                        or (item.get("md5") and item["md5"] != md5.hexdigest())
                        or (
                            declared_size is not None
                            and (type(declared_size) is not int or declared_size != size)
                        )
                    ):
                        asset.integrity = "FAILED"
                    else:
                        asset.integrity = "VERIFIED"
                    rel = path.relative_to(factory.data_root).as_posix()
                    record = (
                        (
                            await self.db.execute(
                                select(FileRecordModel).where(FileRecordModel.storage_path == rel)
                            )
                        )
                        .scalars()
                        .all()
                    )
                    if any(
                        r.user_id != task.user_id
                        or r.task_id != task.id
                        or r.owner_scope != "personal"
                        for r in record
                    ):
                        raise AuthorizationError("Artifact belongs to another execution")
                    valid = [
                        r for r in record if r.status == "active" and r.lifecycle_status == "active"
                    ]
                    if len(valid) > 1:
                        raise ConflictError("Ambiguous artifact registration")
                    if valid:
                        if valid[0].size != size or (
                            valid[0].checksum and valid[0].checksum != actual
                        ):
                            asset.integrity = "FAILED"
                            graph.gaps.append("FILE_RECORD_INTEGRITY_MISMATCH")
                        if not valid[0].checksum:
                            graph.gaps.append("FILE_RECORD_FINGERPRINT_UNKNOWN")
                        asset.file_record_id = valid[0].id
                        asset.file_url = f"/api/v1/files/{valid[0].id}/download"
                    else:
                        graph.gaps.append("ARTIFACT_REGISTRATION_MISSING")
                except FileNotFoundError:
                    asset.integrity = "MISSING"
                except (OSError, ValidationError, ConflictError) as exc:
                    asset.integrity = (
                        "MISSING" if isinstance(exc.__cause__, FileNotFoundError) else "FAILED"
                    )
                graph.artifacts.append(asset)
            graph.result_integrity = (
                "FAILED"
                if any(a.integrity == "FAILED" for a in graph.artifacts)
                else "MISSING"
                if any(a.integrity == "MISSING" for a in graph.artifacts)
                else "VERIFIED"
            )
            # Internal reconciliation paths never appear in DTOs or Agent output.
            self._verified_paths = [
                (found.parent / relative_file(item["path"]), asset)
                for item, asset in zip(declared, graph.artifacts, strict=True)
            ]
        except AuthorizationError:
            raise
        except (ValueError, KeyError, TypeError, OSError, ValidationError, ConflictError):
            graph.result_integrity = "FAILED"
            graph.gaps.append("RESULT_MANIFEST_INVALID")

    async def _reports(self, graph: ResearchProvenance) -> None:
        reports = (
            (
                await self.db.execute(
                    select(ReportModel)
                    .where(
                        ReportModel.task_id == graph.task_id, ReportModel.user_id == graph.owner_id
                    )
                    .order_by(ReportModel.created_at)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        factory = get_path_factory()
        for report in reports:
            if report.report_kind not in {"scientific", "reproducibility", "delivery"}:
                continue
            integrity = "UNKNOWN"
            files = (
                (
                    await self.db.execute(
                        select(ReportFileModel).where(ReportFileModel.report_id == report.id)
                    )
                )
                .scalars()
                .all()
            )
            current = (
                report.result_observation_id == graph.result_observation_id
                and graph.result_observation_id is not None
            )
            if report.snapshot_id:
                from cygnusx.application.services.reproducible_report_service import (
                    validate_snapshot_row,
                )

                snapshot = await self.db.get(ReportSnapshotModel, report.snapshot_id)
                research = (
                    (snapshot.payload.get("research_delivery") or {})
                    if snapshot
                    and snapshot.user_id == graph.owner_id
                    and snapshot.task_id == graph.task_id
                    else {}
                )
                if snapshot is not None:
                    try:
                        validate_snapshot_row(snapshot)
                    except ValueError:
                        research = {}
                current = (
                    str(graph.result_observation_id) == research.get("result_observation_id")
                    and graph.result_observation_id is not None
                )
            if files:
                states = []
                for file in files:
                    file_integrity = "VERIFIED"
                    try:
                        if time.monotonic() > self._capture_deadline:
                            raise ValidationError("Capture time budget")
                        path = Path(file.path)
                        path = path if path.is_absolute() else factory.data_root / path
                        with open_owned_file(
                            path, factory.user_root(str(graph.owner_id))
                        ) as stream:
                            actual, size = checksum(
                                stream,
                                ValidationLimits(
                                    max_bytes=max(
                                        0,
                                        get_settings().research_artifact_max_bytes
                                        - self._captured_bytes,
                                    )
                                ),
                            )
                        self._captured_bytes += size
                        if not file.sha256 and file_integrity == "VERIFIED":
                            file_integrity = "UNKNOWN"
                        elif file.sha256 != actual or file.size != size:
                            file_integrity = "FAILED"
                    except FileNotFoundError:
                        file_integrity = "MISSING"
                    except (ValidationError, OSError) as exc:
                        file_integrity = (
                            "MISSING" if isinstance(exc.__cause__, FileNotFoundError) else "FAILED"
                        )
                    states.append(file_integrity)
                integrity = next(
                    (state for state in ("FAILED", "MISSING", "UNKNOWN") if state in states),
                    "VERIFIED",
                )
            if integrity == "VERIFIED" and (
                report.status != "completed"
                or (not current and graph.dataset_version_id is not None)
            ):
                integrity = "UNKNOWN"
            graph.reports.append(
                ResearchReportLink(
                    report_id=report.id,
                    kind=report.report_kind,
                    state=report.status,
                    integrity=integrity,
                    result_observation_id=report.result_observation_id,
                    report_url=f"/reports?reportId={report.id}",
                )
            )
        jobs = (
            (
                await self.db.execute(
                    select(ReportGenerationJobModel)
                    .where(
                        ReportGenerationJobModel.task_id == graph.task_id,
                        ReportGenerationJobModel.user_id == graph.owner_id,
                    )
                    .order_by(ReportGenerationJobModel.created_at)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        graph.report_jobs = [
            {
                "job_id": str(job.id),
                "kind": "scientific"
                if job.template_version == "scientific-counts-v1"
                else "reproducibility",
                "state": job.status,
                "error_code": job.error_code,
                "retryable": job.retryable,
            }
            for job in jobs
        ]
        if jobs and jobs[-1].status == "failed":
            graph.gaps.append("EVIDENCE_REPORT_JOB_FAILED")
        if not any(r.kind == "scientific" and r.integrity == "VERIFIED" for r in graph.reports):
            graph.gaps.append("SCIENTIFIC_REPORT_NOT_VERIFIED")
        if not any(
            r.kind == "reproducibility" and r.integrity == "VERIFIED" for r in graph.reports
        ):
            graph.gaps.append("EVIDENCE_REPORT_NOT_VERIFIED")

    async def report(self, owner: UUID, report_id: UUID) -> ResearchProvenance:
        report = await self.db.get(ReportModel, report_id)
        if not report or report.user_id != owner:
            raise NotFoundError("Report not found")
        if report.task_id is None:
            raise ValidationError("External reports do not have platform execution provenance")
        return await self.task(owner, report.task_id)

    async def reconcile(self, owner: UUID, task_id: UUID) -> ResearchProvenance:
        require_research_write()
        task, link = await self.task_scope(owner, task_id)
        if not link:
            raise ValidationError("Historical provenance cannot be fabricated")
        # Real PostgreSQL Task lock serializes existing-output registration, never compute replay.
        await self.db.execute(select(TaskModel).where(TaskModel.id == task.id).with_for_update())
        graph = await self.task(owner, task_id, include_reports=False)
        if graph.compute_state not in {"success", "completed", "failed", "cancelled"}:
            return graph
        if graph.artifacts:
            registry = FileRegistry(self.db)
            from cygnusx.application.services.file_service import ensure_directory_chain

            for path, artifact in getattr(self, "_verified_paths", []):
                if artifact.integrity != "VERIFIED":
                    continue
                directory = path.parent.relative_to(
                    get_path_factory().user_root(str(owner))
                ).as_posix()
                await ensure_directory_chain(self.db, owner, directory)
                record = await registry.register(
                    owner,
                    path,
                    source=FileSource.PIPELINE,
                    task_id=task_id,
                    directory=directory,
                    checksum=artifact.sha256,
                )
                artifact.file_record_id = record.id
                artifact.file_url = f"/api/v1/files/{record.id}/download"
            graph.gaps = [gap for gap in graph.gaps if gap != "ARTIFACT_REGISTRATION_MISSING"]
        graph.gaps = [gap for gap in graph.gaps if gap != "RESULT_OBSERVATION_STALE"]
        payload = observation_payload(graph)
        fingerprint = digest(payload)
        observation = (
            await self.db.execute(
                select(ResultObservationModel).where(
                    ResultObservationModel.task_id == task_id,
                    ResultObservationModel.evidence_digest == fingerprint,
                )
            )
        ).scalar_one_or_none()
        if observation is None:
            observation = ResultObservationModel(
                user_id=owner,
                project_id=graph.project_id,
                analysis_link_id=link.id,
                task_id=task_id,
                evidence_digest=fingerprint,
                manifest_sha256=graph.manifest_sha256,
                payload=payload,
            )
            self.db.add(observation)
            await self.db.flush()
        if (
            graph.result_integrity == "VERIFIED"
            and graph.input_integrity == "VERIFIED"
            and not any(
                g in graph.gaps
                for g in (
                    "MANIFEST_IDENTITY_UNKNOWN",
                    "MANIFEST_INPUT_BINDING_UNKNOWN",
                    "RESULT_MANIFEST_INVALID",
                )
            )
        ):
            from cygnusx.application.services.report_service import ReportService

            await ReportService(self.db).register_verified_scientific_result(
                owner, task, observation, getattr(self, "_verified_paths", [])
            )
        await self.db.flush()
        return await self.task(owner, task_id)
