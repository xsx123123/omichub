"""报告应用服务"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.schemas.report import (
    ReportFileResponse,
    ReportFilterParams,
    ReportListResponse,
    ReportResponse,
    ReportVersionTreeResponse,
)
from cygnusx.application.schemas.report_delivery import BioReportRenderRequest
from cygnusx.application.schemas.report_snapshot import ReportSnapshot
from cygnusx.application.schemas.research_delivery import ResearchArtifact
from cygnusx.application.services.bioreport_adapter import BioReportAdapter
from cygnusx.application.services.flow_service import FlowService
from cygnusx.application.services.report_archive import read_archive
from cygnusx.application.services.reproducible_report_service import validate_snapshot_row
from cygnusx.application.services.research_delivery_service import (
    DeliveryInput,
    ResearchDeliveryBuilder,
)
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from cygnusx.domain.file.value_objects import FileSource
from cygnusx.infrastructure.database.models.report import (
    ReportFileModel,
    ReportModel,
    ReportSnapshotModel,
)
from cygnusx.infrastructure.database.models.result_observation import ResultObservationModel
from cygnusx.infrastructure.database.models.task import TaskModel
from cygnusx.infrastructure.database.repositories.report_repository import (
    ReportRepositoryImpl,
)
from cygnusx.infrastructure.storage import get_path_factory, get_storage_backend
from cygnusx.infrastructure.storage.backend import StorageBackend
from cygnusx.infrastructure.storage.file_registry import FileRegistry


class ReportService:
    """报告应用服务"""

    def __init__(
        self,
        db: AsyncSession,
        backend: StorageBackend | None = None,
    ):
        self._db = db
        self._repo = ReportRepositoryImpl(db)
        self._flow_service = FlowService()
        self._settings = get_settings()
        self._factory = get_path_factory()
        self._backend = backend or get_storage_backend()

    async def _require_research_scope(self, model: ReportModel) -> None:
        if getattr(self._settings, "research_delivery_read_enabled", False):
            from cygnusx.application.services.research_provenance_service import (
                ResearchProvenanceService,
            )

            service = ResearchProvenanceService(self._db)
            await service.repo.require_module(model.user_id, "reports")
            task = await self._db.get(TaskModel, model.task_id)
            if task is not None:
                await service.task_scope(model.user_id, task.id)

    async def register_verified_scientific_result(
        self,
        owner: UUID,
        task: TaskModel,
        observation: ResultObservationModel,
        artifacts: list[tuple[Path, ResearchArtifact]],
    ) -> ReportModel | None:
        """Register an existing verified scientific HTML; never generate analysis or invent HTML."""
        if task.user_id != owner or observation.user_id != owner or observation.task_id != task.id:
            raise AuthorizationError("Scientific report scope mismatch")
        existing = (
            await self._db.execute(
                select(ReportModel)
                .where(
                    ReportModel.user_id == owner,
                    ReportModel.task_id == task.id,
                    ReportModel.result_observation_id == observation.id,
                    ReportModel.report_kind == "scientific",
                )
                .order_by(ReportModel.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            from cygnusx.domain.dataset.validation import (
                ValidationLimits,
                checksum,
                open_owned_file,
            )

            files = (
                (
                    await self._db.execute(
                        select(ReportFileModel).where(
                            ReportFileModel.report_id == existing.id,
                            ReportFileModel.is_primary.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if len(files) == 1:
                try:
                    with open_owned_file(
                        Path(files[0].path), self._factory.user_root(str(owner))
                    ) as stream:
                        sha, size = checksum(
                            stream,
                            ValidationLimits(max_bytes=self._settings.research_artifact_max_bytes),
                        )
                    if files[0].sha256 == sha and files[0].size == size:
                        return existing
                except (OSError, ValueError, ValidationError):
                    pass
            # Repair creates a new version and fresh archive, preserving the missing/failed version.
        candidates = [
            (path, asset)
            for path, asset in artifacts
            if asset.category == "report"
            and path.suffix.lower() == ".html"
            and asset.integrity == "VERIFIED"
            and asset.file_record_id is not None
            and asset.sha256
            and asset.size
        ]
        if len(candidates) != 1:
            return None
        path, asset = candidates[0]
        previous = (
            await self._db.execute(
                select(ReportModel)
                .where(
                    ReportModel.user_id == owner,
                    ReportModel.task_id == task.id,
                    ReportModel.report_kind == "scientific",
                )
                .order_by(ReportModel.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        report = ReportModel(
            id=uuid.uuid4(),
            user_id=owner,
            task_id=task.id,
            flow_id=task.flow_id,
            flow_name=task.flow_id,
            flow_version=str(observation.payload.get("flow", {}).get("version") or ""),
            title="Scientific analysis report",
            status="completed",
            report_kind="scientific",
            result_observation_id=observation.id,
            created_at=now,
            completed_at=now,
            parent_id=previous.id if previous else None,
            version=previous.version + 1 if previous else 1,
        )
        self._db.add(report)
        await self._db.flush()
        self._db.add(
            ReportFileModel(
                report_id=report.id,
                name="Scientific report.html",
                type="html",
                size=asset.size,
                path=str(path),
                is_primary=True,
                sha256=asset.sha256,
                file_record_id=asset.file_record_id,
            )
        )
        await self._db.flush()
        return report

    def _resolve_report_path(self, path: str) -> Path:
        """校验报告文件路径必须位于 storage_root 内，防止路径穿越。

        历史数据可能存的是绝对路径，故先 resolve 再 relative_to 校验。
        """
        if not path:
            raise NotFoundError("报告路径不能为空")
        target = Path(path).resolve()
        try:
            target.relative_to(self._factory.data_root.resolve())
        except ValueError as exc:
            raise AuthorizationError("非法报告路径：路径越权") from exc
        return target

    def _rel_path(self, abs_path: Path) -> str:
        """将已校验的绝对路径转为相对 data_root 的路径（供 StorageBackend 使用）。"""
        return self._factory.relative_to_root(abs_path)

    async def _file_nonempty(self, rel_path: str) -> bool:
        """存在且大小非零——把"存在即 completed"收紧为"存在且非空"。"""
        stat_info = await self._backend.stat(rel_path)
        return bool(
            stat_info and not stat_info.get("is_dir") and int(stat_info.get("size") or 0) > 0
        )

    async def _load_result_manifest(self, work_path: Path) -> tuple[dict[str, Any] | None, Path]:
        """按 ARDP §6.2 兜底顺序发现 result_manifest.json；缺失/解析失败返回 (None, root)。

        解析失败只记 WARNING 并回退旧约定（manifest 是流程侧新契约，不得打断存量注册）。
        """
        for root in (work_path, work_path.parent / "data_deliver", work_path / "data_deliver"):
            rel = self._rel_path(root / "result_manifest.json")
            if not await self._backend.exists(rel):
                continue
            try:
                raw = await self._backend.read(rel)
                manifest = json.loads(raw.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("result_manifest.json 解析失败（{}），回退旧约定: {}", rel, exc)
                return None, root
            if not isinstance(manifest, dict):
                logger.warning("result_manifest.json 顶层不是对象（{}），回退旧约定", rel)
                return None, root
            return manifest, root
        return None, work_path

    async def _evaluate_result_manifest(
        self, manifest: dict[str, Any], root: Path
    ) -> tuple[str | None, str | None, str]:
        """校验 manifest 声明的产物文件：真实存在、大小非零、md5（若声明）一致。

        返回 (status, primary_html_rel, note)；status=None 表示 manifest 缺关键字段，
        调用方回退旧约定判定。校验失败不抛异常——落 failed + 结构化 WARNING 留痕。
        """
        raw_run = manifest.get("run")
        run = raw_run if isinstance(raw_run, dict) else {}
        run_status = str(run.get("status") or "")
        if not manifest.get("manifest_version") or run_status not in {
            "completed",
            "completed_no_report",
            "failed",
            "aborted",
        }:
            logger.warning(
                "result_manifest.json 缺少 manifest_version/run.status（{}），回退旧约定", root
            )
            return None, None, ""

        failures: list[str] = []
        for entry in manifest.get("files") or []:
            if not isinstance(entry, dict):
                continue
            rel = str(entry.get("path") or "").strip()
            if not rel or rel.endswith("/") or str(entry.get("type") or "") == "dir":
                continue
            failure = await self._check_manifest_file(root, rel, str(entry.get("md5") or ""))
            if failure:
                failures.append(failure)
        raw_report = manifest.get("report")
        report_block = raw_report if isinstance(raw_report, dict) else {}
        entry_rel = str(report_block.get("entry") or "").strip()
        primary_html_rel: str | None = None
        if entry_rel:
            failure = await self._check_manifest_file(root, entry_rel, "")
            if failure:
                failures.append(failure)
            else:
                primary_html_rel = self._rel_path((root / entry_rel).resolve())

        if run_status in {"failed", "aborted"}:
            raw_error = manifest.get("error")
            error = raw_error if isinstance(raw_error, dict) else {}
            message = str(error.get("message") or "")[:200]
            note = f"流程终态 {run_status}" + (f"：{message}" if message else "")
            return "failed", None, note
        if failures:
            logger.warning("result_manifest 产物校验失败（{}）: {}", root, failures)
            return "failed", None, f"产物校验失败：{'；'.join(failures[:5])}"[:500]
        return "completed", primary_html_rel, ""

    @staticmethod
    def _resolve_within(root: Path, rel: str) -> Path | None:
        """把 manifest 声明的相对路径解析到 root 内；越权（.. 逃逸）返回 None。"""
        resolved_root = root.resolve()
        target = (resolved_root / rel).resolve()
        try:
            target.relative_to(resolved_root)
        except ValueError:
            return None
        return target

    async def _check_manifest_file(self, root: Path, rel: str, md5: str) -> str:
        """单个 manifest 声明文件的存在性/非空/md5 校验；通过返回空串，失败返回原因。"""
        target = self._resolve_within(root, rel)
        if target is None:
            return f"{rel} 路径越权（禁止 .. 逃逸）"
        storage_rel = self._rel_path(target)
        stat_info = await self._backend.stat(storage_rel)
        if not stat_info or stat_info.get("is_dir"):
            return f"{rel} 不存在"
        if int(stat_info.get("size") or 0) <= 0:
            return f"{rel} 大小为零"
        expected_md5 = md5.strip().lower()
        if expected_md5:
            try:
                content = await self._backend.read(storage_rel)
            except Exception as exc:  # noqa: BLE001
                return f"{rel} 读取失败（{exc}）"
            if hashlib.md5(content).hexdigest() != expected_md5:  # noqa: S324 - 对齐交付协议 md5 字段
                return f"{rel} md5 与声明不一致"
        return ""

    async def list_reports(
        self,
        user_id: str,
        params: ReportFilterParams,
    ) -> ReportListResponse:
        """获取用户报告列表"""
        items, total = await self._repo.list_by_user(
            UUID(user_id),
            task_id=params.task_id,
            keyword=params.keyword,
            flow_id=params.flow_id,
            status=params.status,
            date_range=params.date_range,
            is_starred=params.is_starred,
            page=params.page,
            page_size=params.page_size,
        )
        return ReportListResponse(
            items=[_model_to_response(item) for item in items],
            total=total,
        )

    async def get_report(self, report_id: UUID, user_id: str) -> ReportResponse:
        """获取报告详情"""
        model = await self._repo.get_by_id(report_id)
        if model is None or str(model.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(model)
        return _model_to_response(model)

    async def list_versions(self, report_id: UUID, user_id: str) -> ReportVersionTreeResponse:
        """返回指定报告所属的完整版本树。"""
        target = await self._repo.get_by_id(report_id)
        if target is None or str(target.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(target)

        candidates = await self._repo.list_version_candidates(UUID(user_id))
        by_id = {item.id: item for item in candidates}
        by_id[target.id] = target

        root = target
        visited: set[UUID] = set()
        while root.parent_id is not None:
            if root.id in visited:
                raise NotFoundError("报告版本树异常")
            visited.add(root.id)
            parent = by_id.get(root.parent_id)
            if parent is None:
                break
            root = parent

        family_ids = {root.id}
        changed = True
        while changed:
            changed = False
            for item in candidates:
                if item.parent_id in family_ids and item.id not in family_ids:
                    family_ids.add(item.id)
                    changed = True

        family = [item for item in candidates if item.id in family_ids]
        if root.id not in {item.id for item in family}:
            family.append(root)
        family.sort(key=lambda item: (item.version, item.created_at, str(item.id)))
        return ReportVersionTreeResponse(
            root_id=root.id,
            current_id=target.id,
            items=[_model_to_response(item) for item in family],
        )

    async def preview_html(self, report_id: UUID, user_id: str, *, strict: bool = False) -> str:
        """获取报告 HTML 预览内容"""
        model = await self._repo.get_by_id(report_id)
        if model is None or str(model.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(model)

        if strict and model.status != "completed":
            if model.status == "expired":
                raise ConflictError("报告已过期，请重新生成", code="REPORT_EXPIRED")
            raise ConflictError("报告尚未完成，暂时无法预览", code="REPORT_NOT_READY")

        primary = next((f for f in model.files if f.is_primary and f.type == "html"), None)
        if primary is None:
            primary = next((f for f in model.files if f.type == "html"), None)
        if primary is None:
            if strict:
                raise NotFoundError("未找到可预览的 HTML 报告", code="REPORT_HTML_MISSING")
            return "<p>未找到可预览的 HTML 报告</p>"

        target = self._authorized_file_path(model, primary.path)
        rel_path = self._rel_path(target)
        if strict and self._backend.name == "local":
            # Preserve the registered lexical path for the no-follow FD reader.
            # Resolving a symlink first would hide a substituted file/parent.
            registered = Path(primary.path)
            try:
                if ".." in registered.parts:
                    raise ValueError("parent traversal")
                rel_path = registered.relative_to(self._factory.data_root.absolute()).as_posix()
            except ValueError as exc:
                raise AuthorizationError("非法报告路径：路径越权") from exc
        if not await self._backend.exists(rel_path):
            if strict or model.report_kind in {"reproducibility", "delivery"}:
                raise NotFoundError("报告文件已不可用，请联系管理员")
            return "<p>报告文件已丢失，请尝试下载</p>"
        if strict:
            maximum = self._settings.report_preview_max_bytes
            info = await self._backend.stat(rel_path)
            if info and int(info.get("size") or 0) > maximum:
                raise ValidationError("报告超过在线预览大小限制，请下载查看", code="REPORT_TOO_LARGE")
            try:
                content = await read_archive(
                    self._backend, self._factory, rel_path, limit=maximum + 1
                )
            except (OSError, NotFoundError) as exc:
                raise NotFoundError("报告文件当前无法读取") from exc
            if not content:
                raise NotFoundError("报告文件为空，请重新生成", code="REPORT_HTML_EMPTY")
            if len(content) > maximum:
                raise ValidationError("报告超过在线预览大小限制，请下载查看", code="REPORT_TOO_LARGE")
            self._verify_report_bytes(primary.sha256, primary.size, content)
            return content.decode("utf-8", errors="replace")
        try:
            content = (
                await read_archive(self._backend, self._factory, rel_path)
                if primary.sha256
                else await self._backend.read(rel_path)
            )
        except Exception as exc:
            raise NotFoundError("报告文件当前无法读取") from exc
        self._verify_report_bytes(primary.sha256, primary.size, content)
        return content.decode("utf-8", errors="replace")

    def _authorized_file_path(self, model: ReportModel, path: str) -> Path:
        target = self._resolve_report_path(path)
        if model.report_kind in {"reproducibility", "delivery"}:
            root = self._factory.user_root(str(model.user_id)).absolute()
            if root.resolve() != root or not target.is_relative_to(root):
                raise AuthorizationError("报告文件不属于当前用户")
        return target

    @staticmethod
    def _verify_report_bytes(sha256: str | None, size: int, content: bytes) -> None:
        if sha256 and (len(content) != size or hashlib.sha256(content).hexdigest() != sha256):
            raise ConflictError("报告文件完整性校验失败，请联系管理员")

    async def download_file(self, report_id: UUID, file_id: UUID, user_id: str) -> Path:
        """获取报告文件路径"""
        model = await self._repo.get_by_id(report_id)
        if model is None or str(model.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(model)

        file_model = await self._repo.get_file_by_id(file_id)
        if file_model is None or file_model.report_id != report_id:
            raise NotFoundError("文件不存在")

        rel_path = self._rel_path(self._authorized_file_path(model, file_model.path))
        if not await self._backend.exists(rel_path):
            raise NotFoundError("文件已丢失")
        if file_model.sha256:
            self._verify_report_bytes(
                file_model.sha256,
                file_model.size,
                await read_archive(self._backend, self._factory, rel_path),
            )
        return await self._backend.get_local_path(rel_path)

    async def delete_report(self, report_id: UUID, user_id: str) -> None:
        """删除报告（仅删除记录）"""
        model = await self._repo.get_by_id(report_id)
        if model is None or str(model.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(model)
        await self._repo.delete(report_id)

    async def toggle_star(self, report_id: UUID, user_id: str, is_starred: bool) -> ReportResponse:
        """切换收藏状态"""
        model = await self._repo.get_by_id(report_id)
        if model is None or str(model.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(model)
        model.is_starred = is_starred
        await self._repo.save(model)
        return _model_to_response(model)

    async def mark_read(self, report_id: UUID, user_id: str) -> ReportResponse:
        """标记已读"""
        model = await self._repo.get_by_id(report_id)
        if model is None or str(model.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(model)
        model.is_read = True
        await self._repo.save(model)
        return _model_to_response(model)

    async def create_report_from_task(
        self,
        task_id: str,
        user_id: str,
        flow_id: str,
        work_dir: str,
        sample_count: int,
        duration: int,
    ) -> ReportModel | None:
        """任务完成后扫描目录并创建报告记录"""
        existing = await self._repo.get_by_task_id(UUID(task_id))
        if existing is not None:
            return existing

        flow_detail = self._flow_service.get_flow(flow_id)
        flow_name = flow_detail.meta.name if flow_detail else flow_id
        flow_version = flow_detail.meta.version if flow_detail else ""
        flow_icon = flow_detail.meta.icon or "📄" if flow_detail else "📄"

        now = datetime.now()
        title = f"{flow_name} 分析报告"
        description = ""

        work_path = Path(work_dir)
        report_dir = work_path / "Analysis_Report"
        html_path = report_dir / "index.html"

        # 尝试从 project_summary.json 读取更丰富的元信息
        summary_path = work_path / "report_data" / "project_summary.json"
        summary_rel = self._rel_path(summary_path)
        legacy_summary: dict[str, Any] = {}
        if await self._backend.exists(summary_rel):
            try:
                summary_bytes = await self._backend.read(summary_rel)
                summary = json.loads(summary_bytes.decode("utf-8"))
                if isinstance(summary, dict):
                    legacy_summary = summary
                project_meta = summary.get("project_meta", {})
                stats = summary.get("stats", {})
                if project_meta.get("client"):
                    title = f"{project_meta.get('client')} - {flow_name} 分析报告"
                description = (
                    f"物种: {project_meta.get('species', 'N/A')} | "
                    f"基因组: {project_meta.get('genome_version', 'N/A')} | "
                    f"样本数: {stats.get('total_samples', sample_count)}"
                )
                sample_count = stats.get("total_samples", sample_count) or sample_count
            except Exception:  # noqa: BLE001
                pass

        html_rel = self._rel_path(html_path)
        html_ready = await self._file_nonempty(html_rel)
        status = "completed" if html_ready else "failed"

        # ARDP（Protocol/分析流程结果交付协议_v1.md）：产物目录存在 result_manifest.json
        # 时优先按 manifest 判定（声明产物存在/非空/md5 比对）；缺失或无效时回退旧约定。
        manifest, manifest_root = await self._load_result_manifest(work_path)
        if manifest is not None:
            manifest_status, manifest_html_rel, note = await self._evaluate_result_manifest(
                manifest, manifest_root
            )
            if manifest_status is not None:
                status = manifest_status
                if manifest_html_rel:
                    html_rel = manifest_html_rel
                    html_ready = True
                    html_path = Path(self._factory.data_root) / html_rel
                    report_dir = html_path.parent
                if note:
                    description = f"{description} | {note}" if description else note

        report = ReportModel(
            id=uuid.uuid4(),
            task_id=UUID(task_id),
            user_id=UUID(user_id),
            flow_id=flow_id,
            flow_name=flow_name,
            flow_version=flow_version,
            flow_icon=flow_icon,
            title=title,
            description=description,
            status=status,
            sample_count=sample_count,
            duration=duration,
            created_at=now,
            completed_at=now if status == "completed" else None,
        )
        await self._repo.create(report)

        if html_ready:
            stat_info = await self._backend.stat(html_rel)
            file_model = ReportFileModel(
                id=uuid.uuid4(),
                report_id=report.id,
                name=html_path.name,
                type="html",
                size=stat_info["size"] if stat_info else 0,
                path=str(html_path),
                is_primary=True,
            )
            self._db.add(file_model)
            await self._db.flush()

            # 报告文件同时注册到统一文件索引（source=REPORT），使 AI 助手可见
            try:
                path_factory = get_path_factory()
                report_directory = report_dir.relative_to(
                    path_factory.user_root(user_id)
                ).as_posix()
                await FileRegistry(self._db).register(
                    UUID(user_id),
                    html_path,
                    source=FileSource.REPORT,
                    task_id=UUID(task_id),
                    directory=report_directory,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("报告文件注册到 file_records 失败（非阻塞）: {}", exc)

            task_model = await self._db.get(TaskModel, UUID(task_id))
            if task_model is not None:
                from cygnusx.application.services.report_paths_registry import (
                    ReportPathsRegistryService,
                )

                await ReportPathsRegistryService(self._db).register(
                    report,
                    task_model,
                    manifest_root,
                    legacy_summary=legacy_summary,
                    manifest=manifest,
                )

            await self._db.refresh(report)

        return report

    async def register_project_report_file(
        self, *, owner: UUID, project: UUID, job_id: UUID,
        archive_path: str, content: bytes, file_type: str,
    ) -> ReportFileModel:
        """Register already-published project bytes using the shared file registry."""
        from cygnusx.application.services.file_service import ensure_directory_chain
        from cygnusx.application.services.project_delivery_service import ProjectDeliveryService
        from cygnusx.infrastructure.database.models.project_report import ProjectReportJobModel

        await ProjectDeliveryService(self._db).authorize(owner, project)
        job = await self._db.get(ProjectReportJobModel, job_id, populate_existing=True)
        if not job or (job.user_id, job.project_id) != (owner, project):
            raise NotFoundError("Project report unavailable")
        if file_type not in {"html", "pdf"} or not content:
            raise ValidationError("Invalid project report artifact")
        path = self._factory.data_root / archive_path
        root = self._factory.user_root(str(owner))
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise AuthorizationError("Project report archive path denied")
        published = await read_archive(self._backend, self._factory, archive_path)
        sha = hashlib.sha256(content).hexdigest()
        self._verify_report_bytes(sha, len(content), published)
        existing_file = await self._db.scalar(select(ReportFileModel).where(
            ReportFileModel.project_report_job_id == job.id, ReportFileModel.type == file_type
        ))
        if existing_file is not None:
            if (existing_file.path, existing_file.sha256, existing_file.size) != (str(path), sha, len(content)):
                raise ConflictError("Published project report cannot be replaced")
            return existing_file
        directory = path.parent.relative_to(root).as_posix()
        await ensure_directory_chain(self._db, owner, directory)
        record = await FileRegistry(self._db, self._factory, self._backend).register(
            owner, path, source=FileSource.REPORT, directory=directory, checksum=sha,
        )
        if (
            record.user_id != owner or record.task_id is not None
            or record.owner_scope != "personal" or record.status != "active"
            or record.lifecycle_status != "active" or record.source != "report"
            or record.checksum != sha or record.size != len(content)
        ):
            raise ConflictError("Project report registration mismatch")
        file = ReportFileModel(
            project_report_job_id=job.id, name=f"index.{file_type}", type=file_type,
            path=str(path), size=len(content), sha256=sha, file_record_id=record.id,
            is_primary=file_type == "html",
        )
        self._db.add(file)
        await self._db.flush()
        return file

    async def register_reproducibility_report(
        self,
        *,
        snapshot: ReportSnapshot,
        snapshot_id: UUID,
        template_version: str,
        archive_path: str,
        size: int,
        sha256: str,
        evidence_partial: bool,
        pdf_archive_path: str | None = None,
        pdf_size: int | None = None,
        pdf_sha256: str | None = None,
    ) -> ReportModel:
        """Register verified bytes in the existing centre, directories and file index.

        Caller holds the per-Task worker lock. This transaction also marks the Job ready.
        Historical Flow metadata is never replaced by today's catalog version.
        """
        from cygnusx.application.services.file_service import ensure_directory_chain

        owner = snapshot.source_execution.owner_id
        task_id = snapshot.source_execution.task_id
        if task_id is None:
            raise ValueError("Audit report requires Task identity")
        path = self._factory.data_root / archive_path
        root = self._factory.user_root(str(owner)).absolute()
        if root.resolve() != root or not path.resolve().is_relative_to(root):
            raise AuthorizationError("报告归档路径越权")
        directory = path.parent.relative_to(root).as_posix()
        await ensure_directory_chain(self._db, owner, directory)
        # Keep report files out of the evidence adapter's Task artifact set: otherwise
        # each generation would capture its previous audit and create a new digest.
        record = await FileRegistry(self._db, self._factory, self._backend).register(
            owner,
            path,
            source=FileSource.REPORT,
            directory=directory,
            checksum=sha256,
        )
        if record.source != "report" or record.checksum not in {"", sha256}:
            raise ConflictError("报告文件索引与已校验字节不一致")
        record.storage_backend = self._backend.name
        record.size = size
        record.checksum = sha256
        previous = await self._db.scalar(
            select(ReportModel)
            .where(
                ReportModel.user_id == owner,
                ReportModel.task_id == task_id,
                ReportModel.report_kind == "reproducibility",
            )
            .order_by(ReportModel.version.desc(), ReportModel.created_at.desc())
            .limit(1)
        )
        now = datetime.now(UTC)
        report = ReportModel(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=owner,
            flow_id=str(
                next((f.value for f in snapshot.inputs if f.field == "flow_id"), "rna_seq")
            ),
            flow_name="Counts DEG"
            if snapshot.research_delivery
            and snapshot.research_delivery.flow.get("id") == "counts_deg"
            else "RNA-seq",
            flow_version="",
            flow_icon="📋",
            title="科研可复现执行证据报告",
            description=f"Snapshot {snapshot.snapshot_digest}",
            status="completed",
            sample_count=next(
                (
                    int(f.value)
                    for f in snapshot.inputs
                    if f.field == "sample_count" and isinstance(f.value, int)
                ),
                0,
            ),
            duration=0,
            created_at=now,
            completed_at=now,
            report_kind="reproducibility",
            result_observation_id=snapshot.research_delivery.result_observation_id
            if snapshot.research_delivery
            else None,
            snapshot_id=snapshot_id,
            template_version=template_version,
            evidence_partial=evidence_partial,
            parent_id=previous.id if previous else None,
            version=previous.version + 1 if previous else 1,
        )
        self._db.add(report)
        self._db.add(
            ReportFileModel(
                id=uuid.uuid4(),
                report_id=report.id,
                file_record_id=record.id,
                name="index.html",
                type="html",
                size=size,
                path=str(path),
                is_primary=True,
                sha256=sha256,
            )
        )
        if pdf_archive_path is not None and pdf_size is not None and pdf_sha256 is not None:
            pdf_path = self._factory.data_root / pdf_archive_path
            if not pdf_path.resolve().is_relative_to(root):
                raise AuthorizationError("报告 PDF 归档路径越权")
            self._db.add(
                ReportFileModel(
                    id=uuid.uuid4(),
                    report_id=report.id,
                    name="index.pdf",
                    type="pdf",
                    size=pdf_size,
                    path=str(pdf_path),
                    is_primary=False,
                    sha256=pdf_sha256,
                )
            )
        await self._db.flush()
        return report

    async def build_delivery_package(self, report_id: UUID, user_id: str) -> ReportModel:
        """Package an existing owner-scoped report and its frozen snapshot.

        This only organizes already published bytes. It never runs RNAFlow and
        never captures a replacement snapshot.
        """
        source = await self._repo.get_by_id(report_id)
        if source is None or str(source.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(source)
        from cygnusx.infrastructure.database.models.task import TaskModel

        actual_task = (
            await self._db.execute(
                select(TaskModel)
                .where(TaskModel.id == source.task_id, TaskModel.user_id == source.user_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if actual_task is None or actual_task.user_id != source.user_id:
            raise NotFoundError("报告任务不存在或无权访问")
        if source.status != "completed":
            raise ConflictError("只有已发布报告可以打包")
        if source.report_kind == "delivery":
            raise ConflictError("科研交付包不能再次打包")
        if source.report_kind not in {"scientific", "reproducibility"}:
            raise ConflictError("报告类型不能作为科研交付来源")
        scientific: ReportModel | None = source if source.report_kind == "scientific" else None
        evidence: ReportModel | None = source if source.report_kind == "reproducibility" else None
        opposite = "reproducibility" if scientific else "scientific"
        query = select(ReportModel).where(
            ReportModel.user_id == source.user_id,
            ReportModel.task_id == source.task_id,
            ReportModel.report_kind == opposite,
            ReportModel.status == "completed",
        )
        if source.result_observation_id is not None:
            query = query.where(ReportModel.result_observation_id == source.result_observation_id)
        else:
            query = query.where(ReportModel.result_observation_id.is_(None))
        if (
            source.report_kind == "reproducibility"
            and source.snapshot_id
            and source.result_observation_id is None
        ):
            original_snapshot = await self._db.get(ReportSnapshotModel, source.snapshot_id)
            if original_snapshot is not None:
                query = query.where(
                    or_(
                        ReportModel.completed_at <= original_snapshot.captured_at,
                        and_(
                            ReportModel.completed_at.is_(None),
                            ReportModel.created_at <= original_snapshot.captured_at,
                        ),
                    )
                )
        peer = await self._db.scalar(
            query.order_by(ReportModel.version.desc(), ReportModel.created_at.desc()).limit(1)
        )
        if scientific is not None:
            evidence = peer
        else:
            scientific = peer
        for candidate in (scientific, evidence):
            if candidate is not None:
                if candidate.user_id != source.user_id or candidate.task_id != source.task_id:
                    raise ConflictError("报告来源身份不一致")
                await self._require_research_scope(candidate)
        snapshot_ref = evidence.snapshot_id if evidence else source.snapshot_id
        snapshot_model = (
            await self._db.get(ReportSnapshotModel, snapshot_ref) if snapshot_ref else None
        )
        snapshot: ReportSnapshot | None = None
        if snapshot_ref:
            if (
                snapshot_model is None
                or snapshot_model.user_id != source.user_id
                or snapshot_model.task_id != source.task_id
            ):
                raise ConflictError("报告快照身份不一致")
            try:
                snapshot = validate_snapshot_row(snapshot_model)
            except (TypeError, ValueError) as exc:
                raise ConflictError("报告快照完整性校验失败") from exc
            if source.snapshot_id and source.snapshot_id != snapshot_ref:
                raise ConflictError("报告快照版本不一致")
            for candidate in (scientific, evidence):
                if candidate and candidate.snapshot_id and candidate.snapshot_id != snapshot_ref:
                    raise ConflictError("报告快照版本不一致")
            if source.result_observation_id is not None and (
                snapshot.research_delivery is None
                or snapshot.research_delivery.result_observation_id != source.result_observation_id
            ):
                raise ConflictError("报告观察与冻结快照不一致")
            # Unbound historical scientific reports must not postdate the frozen evidence.
            if scientific is not None and source.result_observation_id is None:
                when = scientific.completed_at or scientific.created_at
                if when and when.replace(tzinfo=UTC) > snapshot_model.captured_at.replace(
                    tzinfo=UTC
                ):
                    scientific = None
        existing = await self._db.scalar(
            select(ReportModel)
            .where(
                ReportModel.user_id == source.user_id,
                ReportModel.task_id == source.task_id,
                ReportModel.report_kind == "delivery",
                ReportModel.snapshot_id == snapshot_ref,
                or_(ReportModel.parent_id == source.id, ReportModel.snapshot_id.is_not(None)),
                ReportModel.template_version == "delivery-v1.1.0",
            )
            .limit(1)
        )
        if existing is not None:
            return existing

        inputs: list[DeliveryInput] = []
        reports = (("Scientific_Report", scientific), ("Reproducibility_Record", evidence))
        seen: set[str] = set()
        scientific_html: bytes | None = None
        bioreport_config: tuple[bytes, str] | None = None
        renderer_versions: set[str] = set()
        for prefix, report in reports:
            available_types: set[str] = set()
            report_files = report.files if report is not None else []
            for file_model in report_files:
                assert report is not None
                logical_name = f"{prefix}.{file_model.type}"
                if logical_name in seen:
                    continue
                seen.add(logical_name)
                available_types.add(file_model.type)
                rel = self._rel_path(self._authorized_file_path(report, file_model.path))
                if not await self._backend.exists(rel):
                    inputs.append(
                        DeliveryInput(
                            logical_name=logical_name,
                            content=None,
                            file_type=file_model.type,
                            source_object=str(file_model.id),
                        )
                    )
                    continue
                content = await read_archive(self._backend, self._factory, rel)
                self._verify_report_bytes(file_model.sha256, file_model.size, content)
                if prefix == "Scientific_Report" and file_model.type == "html":
                    scientific_html = content
                if prefix == "Reproducibility_Record" and file_model.type == "pdf":
                    renderer_versions.add("pandoc-typst")
                if prefix == "Scientific_Report" and file_model.type in {"json", "yaml", "yml"}:
                    lowered = file_model.name.lower()
                    if "bioreport" in lowered or "report_config" in lowered:
                        bioreport_config = (content, file_model.name)
                inputs.append(
                    DeliveryInput(
                        logical_name=logical_name,
                        content=content,
                        file_type=file_model.type,
                        source_object=str(file_model.id),
                        original_artifact_id=file_model.id,
                    )
                )
            for expected_type in ("html", "pdf"):
                expected_name = f"{prefix}.{expected_type}"
                if expected_type not in available_types and expected_name not in seen:
                    seen.add(expected_name)
                    inputs.append(
                        DeliveryInput(
                            logical_name=expected_name,
                            content=None,
                            file_type=expected_type,
                            source_object=f"{report.id if report else source.task_id}:missing:{expected_type}",
                        )
                    )

        renderer_version = ";".join(sorted(renderer_versions)) or "not_used"
        if (
            snapshot is not None
            and bioreport_config is not None
            and not any(
                item.logical_name == "Scientific_Report.pdf" and item.content is not None
                for item in inputs
            )
        ):
            assert snapshot_ref is not None
            rendered_pdf = await self._render_scientific_pdf(
                task_id=source.task_id,
                snapshot_id=snapshot_ref,
                snapshot_digest=snapshot.snapshot_digest,
                html=scientific_html,
                config=bioreport_config,
            )
            if rendered_pdf is not None:
                inputs = [item for item in inputs if item.logical_name != "Scientific_Report.pdf"]
                inputs.append(
                    DeliveryInput(
                        logical_name="Scientific_Report.pdf",
                        content=rendered_pdf,
                        file_type="pdf",
                        source_object="cygnusx.bioreport_adapter",
                        generation="rendered",
                    )
                )
                renderer_versions.add("bioreport-2.0.0")
                renderer_version = ";".join(sorted(renderer_versions))
        inputs.append(
            DeliveryInput(
                logical_name="ReportSnapshot.json",
                content=json.dumps(
                    snapshot.model_dump(mode="json") if snapshot else None,
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8")
                if snapshot
                else None,
                file_type="json",
                source_object=str(snapshot_ref) if snapshot_ref else "NOT_RECORDED",
                generation="generated",
            )
        )
        root = self._factory.user_root(user_id) / "delivery"
        build = ResearchDeliveryBuilder().build(
            snapshot=snapshot,
            snapshot_id=snapshot_ref,
            task_id=source.task_id,
            output_root=root,
            inputs=tuple(inputs),
            renderer_version=renderer_version,
            template_version="delivery-v1.1.0",
        )
        previous = await self._db.scalar(
            select(ReportModel)
            .where(
                ReportModel.user_id == source.user_id,
                ReportModel.task_id == source.task_id,
                ReportModel.report_kind == "delivery",
            )
            .order_by(ReportModel.version.desc())
            .limit(1)
        )
        now = datetime.now(UTC)
        report = ReportModel(
            id=uuid.uuid4(),
            task_id=source.task_id,
            user_id=source.user_id,
            flow_id=source.flow_id,
            flow_name=source.flow_name,
            flow_version=source.flow_version,
            flow_icon="📦",
            title="科研交付包",
            description=(
                "完整交付"
                if build.manifest.evidence_status == "complete"
                else "部分交付，详见缺失文件"
            ),
            status="completed",
            sample_count=source.sample_count,
            duration=source.duration,
            created_at=now,
            completed_at=now,
            report_kind="delivery",
            snapshot_id=snapshot_ref,
            template_version="delivery-v1.1.0",
            evidence_partial=build.manifest.evidence_status == "partial",
            parent_id=source.id,
            version=(previous.version + 1 if previous else 1),
        )
        self._db.add(report)
        for path, file_type, primary in (
            (build.directory / "README.md", "md", False),
            (build.directory / "EvidenceManifest.json", "json", False),
            (build.directory / "ReportSnapshot.json", "json", False),
            (build.directory / "checksums.sha256", "sha256", False),
            (build.zip_path, "zip", True),
        ):
            if file_type == "json" and snapshot is None:
                continue
            content = path.read_bytes()
            self._db.add(
                ReportFileModel(
                    id=uuid.uuid4(),
                    report_id=report.id,
                    name=path.name,
                    type=file_type,
                    size=len(content),
                    path=str(path),
                    is_primary=primary,
                    sha256=hashlib.sha256(content).hexdigest(),
                )
            )
        await self._db.flush()
        return report

    async def _render_scientific_pdf(
        self,
        *,
        task_id: UUID,
        snapshot_id: UUID,
        snapshot_digest: str | None,
        html: bytes | None,
        config: tuple[bytes, str],
    ) -> bytes | None:
        """Render a registered BioReport config without exposing platform files."""
        if snapshot_digest is None:
            return None
        config_bytes, config_name = config
        try:
            with tempfile.TemporaryDirectory(prefix="cygnusx-scientific-pdf-") as temp:
                root = Path(temp)
                config_path = root / config_name
                config_path.write_bytes(config_bytes)
                source_path = root / "report.html"
                if html is not None:
                    source_path.write_bytes(html)
                output_dir = root / "output"
                request = BioReportRenderRequest(
                    task_id=task_id,
                    report_snapshot_id=snapshot_id,
                    report_snapshot_digest=snapshot_digest,
                    scientific_report_source=str(source_path),
                    report_config=str(config_path),
                    output_format="pdf",
                    renderer_version="bioreport-2.0.0",
                    template_version="bioreport-v2",
                )
                result = await asyncio.to_thread(
                    BioReportAdapter(
                        renderer_version="bioreport-2.0.0",
                        template_version="bioreport-v2",
                    ).render,
                    request,
                    output_dir,
                )
                return result.output.read_bytes()
        except (OSError, RuntimeError, ValueError):
            logger.warning(
                "BioReport scientific PDF rendering unavailable; retaining partial delivery"
            )
            return None

    async def object_download(
        self, report_id: UUID, file_id: UUID, user_id: str
    ) -> tuple[bytes, str]:
        """Owner-authorized object-storage HTML download, using the same API surface."""
        model = await self._repo.get_by_id(report_id)
        if model is None or str(model.user_id) != user_id:
            raise NotFoundError("报告不存在")
        await self._require_research_scope(model)
        file = await self._repo.get_file_by_id(file_id)
        if file is None or file.report_id != report_id:
            raise NotFoundError("文件不存在")
        rel = self._rel_path(self._authorized_file_path(model, file.path))
        if not await self._backend.exists(rel):
            raise NotFoundError("文件已丢失")
        try:
            content = await read_archive(self._backend, self._factory, rel)
        except OSError as exc:
            raise NotFoundError("报告文件当前无法读取") from exc
        self._verify_report_bytes(file.sha256, file.size, content)
        return content, file.name

    async def stats(self, user_id: str) -> dict[str, int]:
        """用户报告统计"""
        return await self._repo.count_by_user(UUID(user_id))


def _model_to_response(model: ReportModel) -> ReportResponse:
    return ReportResponse(
        id=model.id,
        task_id=model.task_id,
        user_id=model.user_id,
        flow_id=model.flow_id,
        flow_name=model.flow_name,
        flow_version=model.flow_version,
        flow_icon=model.flow_icon,
        title=model.title,
        description=model.description,
        status=model.status,
        sample_count=model.sample_count,
        duration=model.duration,
        created_at=model.created_at,
        completed_at=model.completed_at,
        is_read=model.is_read,
        is_starred=model.is_starred,
        parent_id=model.parent_id,
        version=model.version,
        report_kind=model.report_kind or "scientific",
        snapshot_id=model.snapshot_id,
        template_version=model.template_version,
        evidence_partial=model.evidence_partial,
        files=[
            ReportFileResponse(
                id=f.id,
                report_id=f.report_id,
                name=f.name,
                type=f.type,
                size=f.size,
                path=(
                    "output/" + f.name
                    if model.report_kind in {"reproducibility", "delivery"}
                    else f.path
                ),
                sha256=f.sha256,
                is_primary=f.is_primary,
                created_at=f.created_at,
            )
            for f in model.files
        ],
    )
