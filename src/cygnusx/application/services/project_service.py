"""项目应用服务 —— 管理用户的分析项目。

Project 是用户视角的"分析项目"聚合根。每个 Project 对应磁盘上
``users/{user_id}/projects/{slug}/`` 目录，下挂多个 Run。

服务职责：
- 列出 / 计数 / 创建 / 删除项目
- 与 Directory 记录同步（创建 Project 时同步创建 Directory）
- 显式同步磁盘项目；读取只查数据库，已删身份通过 tombstone 保留
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.schemas.project import ProjectCapability, ProjectCapabilityStatus
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from cygnusx.infrastructure.database.models.dataset import DatasetIngestionModel, DatasetModel
from cygnusx.infrastructure.database.models.download_execution import (
    DownloadExecutionAdmissionModel,
    DownloadExecutionBudgetModel,
)
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
from cygnusx.infrastructure.database.repositories import DirectoryRepositoryImpl
from cygnusx.infrastructure.storage.path_factory import get_path_factory, project_slug

# 项目删除前的科研保留引用清单：预检查用于给出可解释的 409，数据库 RESTRICT
# 约束最终兜底并发写入。新增指向 projects.id 的外键时必须同步登记，否则只能
# 依赖 IntegrityError 兜底转换。
_RETAINED_REFERENCES: tuple[tuple[str, str, type[Any]], ...] = (
    ("dataset", "数据集", DatasetModel),
    ("dataset_ingestion", "数据导入记录", DatasetIngestionModel),
    ("research_plan", "科研计划", ResearchPlanModel),
    ("result_observation", "结果观察记录", ResultObservationModel),
    ("download_budget", "下载执行预算", DownloadExecutionBudgetModel),
    ("download_admission", "下载执行许可", DownloadExecutionAdmissionModel),
    ("export_job", "项目导出记录", ProjectExportJobModel),
    ("export_request", "导出请求记录", ProjectExportRequestModel),
    ("report_job", "项目报告记录", ProjectReportJobModel),
    ("report_request", "报告请求记录", ProjectReportRequestModel),
)


class ProjectService:
    """项目管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._factory = get_path_factory()

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    PROJECT_STATUSES = ("active", "completed", "handed_over")

    @staticmethod
    def _to_dict(model: ProjectModel) -> dict[str, Any]:
        return {
            "id": str(model.id),
            "name": model.name,
            "slug": model.slug,
            "description": model.description,
            "customer": model.customer,
            # NULL compatibility for the lifecycle01 transition; remove in lifecycle02.
            "status": getattr(model, "status", None) or "active",
            # WP3 任务 3：项目级设置（当前仅 research_mode）；NULL 透出为 None
            "settings": getattr(model, "settings", None)
            if isinstance(getattr(model, "settings", None), dict)
            else None,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    async def list_projects(self, user_id: UUID) -> list[dict[str, Any]]:
        """只读列出数据库中的项目，不推断磁盘目录的项目身份。"""
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.user_id == user_id)
            .order_by(ProjectModel.updated_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_dict(m) for m in result.scalars().all()]

    async def count_projects(self, user_id: UUID) -> int:
        """只读返回数据库中的项目总数。"""
        result = await self._session.execute(
            select(func.count()).select_from(ProjectModel).where(ProjectModel.user_id == user_id)
        )
        return result.scalar_one()

    async def get_project(self, user_id: UUID, project_id: UUID) -> dict[str, Any]:
        stmt = select(ProjectModel).where(
            ProjectModel.id == project_id, ProjectModel.user_id == user_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"项目不存在：{project_id}")
        return self._to_dict(model)

    # ------------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------------
    async def create_project(
        self, user_id: UUID, name: str, description: str = "", customer: str = ""
    ) -> dict[str, Any]:
        """创建新项目。

        - ``slug`` 由 ``project_slug(name)`` 自动生成，保证路径安全
        - 同步在 ``user_directories`` 登记 ``projects/{slug}`` 目录记录
        """
        model, _created = await self.reserve_project_identity(
            user_id, name, description=description, customer=customer
        )
        # 预创建物理目录
        self._factory.project_dir(str(user_id), model.slug).mkdir(parents=True, exist_ok=True)
        (self._factory.project_dir(str(user_id), model.slug) / "runs").mkdir(exist_ok=True)

        await self._session.commit()
        await self._session.refresh(model)
        return self._to_dict(model)

    async def get_or_create_project_by_name(self, user_id: UUID, name: str) -> dict[str, Any]:
        """按名称复用或创建项目（AgentTeams 聊天 Case 建单场景）。

        聊天式 Case 的项目名由需求文本自动生成；删除 Case 不会删除项目，
        用户用同一需求重新建单时 slug 必然撞上存量项目。此时应复用既有项目
        （每个 Case 仍会在其下创建独立的带时间戳 run 目录），而不是把
        "同名项目已存在"抛给用户。slug 被已删除身份（tombstone）保留时
        分配新的可用 slug（-2 起），不复活旧项目身份。
        """
        model, created = await self.reserve_project_identity(user_id, name, reuse_existing=True)
        if not created:
            return self._to_dict(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_dict(model)

    async def reserve_project_identity(
        self,
        user_id: UUID,
        name: str,
        *,
        description: str = "",
        customer: str = "",
        reuse_existing: bool = False,
    ) -> tuple[ProjectModel, bool]:
        """统一的项目身份预留入口（显式创建 / 按名复用 / 会话默认项目共用）。

        - owner 行锁串行化同用户并发创建，保留数据库唯一约束兜底；
        - ``reuse_existing=True``：同 slug 存量项目直接复用；slug 被 tombstone
          保留时分配新的可用 slug，不复活已删除身份；
        - ``reuse_existing=False``：保持显式创建的冲突语义
          （同名项目已存在 / PROJECT_SLUG_RETAINED）；
        - 仅登记目录投影并 flush，不 commit —— 事务边界由调用方控制。

        返回 ``(model, created)``。
        """
        name = (name or "").strip()
        if not name:
            raise ValidationError("项目名不能为空")
        if len(name) > 200:
            raise ValidationError("项目名最长 200 字符")
        customer = (customer or "").strip()
        if len(customer) > 200:
            raise ValidationError("客户名最长 200 字符")
        if len(description) > 2000:
            raise ValidationError("项目描述最长 2000 字符")
        slug = project_slug(name)
        if not slug:
            raise ValidationError("项目名无法生成合法目录 slug")

        await self._lock_owner(user_id)
        existing = await self._find_project_by_slug(user_id, slug)
        if existing is not None:
            if reuse_existing:
                return existing, False
            raise ConflictError(f"同名项目已存在：{slug}")
        if await self._slug_retained(user_id, slug):
            if not reuse_existing:
                raise ConflictError(
                    "该项目目录保留了已删除项目的身份，请使用新项目名",
                    code="PROJECT_SLUG_RETAINED",
                )
            slug = await self._allocate_available_slug(user_id, slug)
        model = ProjectModel(
            user_id=user_id, name=name, slug=slug, description=description, customer=customer
        )
        self._session.add(model)
        await self._register_project_directory(user_id, slug)
        await self._session.flush()
        return model, True

    async def update_project_settings(
        self, user_id: UUID, project_id: UUID, settings: dict[str, Any]
    ) -> dict[str, Any]:
        """按 JSON Merge Patch 合并项目设置。"""
        return await self.update_project(user_id, project_id, {"settings": settings})

    @staticmethod
    def _merge_patch(target: Any, patch: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(target) if isinstance(target, dict) else {}
        for key, value in patch.items():
            if value is None:
                result.pop(key, None)
            elif isinstance(value, dict):
                result[key] = ProjectService._merge_patch(result.get(key), value)
            else:
                result[key] = deepcopy(value)
        return cast(dict[str, Any], result)

    async def update_project(
        self, user_id: UUID, project_id: UUID, changes: dict[str, Any]
    ) -> dict[str, Any]:
        """原子更新元数据与设置，保留 slug；行锁防止并发合并丢更新。"""
        if not changes or set(changes) - {"name", "description", "status", "settings"}:
            raise ValidationError("至少提供 name、description、status、settings 中的一项")
        result = await self._session.execute(
            select(ProjectModel)
            .where(ProjectModel.id == project_id, ProjectModel.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"项目不存在：{project_id}")
        # Validate all fields before mutating the ORM object or committing anything.
        values = dict(changes)
        if "name" in values:
            name = values["name"]
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
                raise ValidationError("项目名不能为空且最长 200 字符")
            values["name"] = name.strip()
        if "description" in values:
            description = values["description"]
            if not isinstance(description, str) or len(description) > 2000:
                raise ValidationError("项目描述须为字符串且最长 2000 字符")
        if "status" in values and values["status"] not in self.PROJECT_STATUSES:
            raise ValidationError(f"非法项目状态（允许 {self.PROJECT_STATUSES}）")
        if "settings" in values:
            patch = values["settings"]
            if patch is not None and not isinstance(patch, dict):
                raise ValidationError("settings 必须是 JSON 对象或 null")
            merged = self._merge_patch(model.settings, patch) if patch is not None else None
            if merged is not None and "research_mode" in merged:
                mode = merged["research_mode"]
                if not isinstance(mode, dict):
                    raise ValidationError("settings.research_mode 必须是 JSON 对象")
                if "enabled" in mode and not isinstance(mode["enabled"], bool):
                    raise ValidationError("settings.research_mode.enabled 必须为布尔值")
            values["settings"] = merged
        previous_status = model.status
        for key, value in values.items():
            setattr(model, key, value)
        await self._session.commit()
        await self._session.refresh(model)
        if model.status != previous_status and model.status in {"completed", "handed_over"}:
            await self._pack_project_sessions(model)
        return self._to_dict(model)

    async def mark_project_status(
        self, user_id: UUID, project_id: UUID, status: str
    ) -> dict[str, Any]:
        """标记项目状态（属主）；completed/handed_over 触发其下会话工作区休眠打包。

        chat_sessions.project_id 存的是 str(projects.id)（已核实线上数据），
        按字符串等值匹配；打包为后台任务，busy 会话跳过记日志。
        """
        status = (status or "").strip().lower()
        if status not in self.PROJECT_STATUSES:
            raise ValidationError(f"非法项目状态：{status}（允许 {self.PROJECT_STATUSES}）")
        return await self.update_project(user_id, project_id, {"status": status})

    async def _pack_project_sessions(self, model: ProjectModel) -> None:
        """项目完成/移交后，其下 studio 会话全部后台休眠打包（幂等，busy 跳过）。"""
        import asyncio

        from loguru import logger

        from cygnusx.application.services.workspace_archive_service import pack_session
        from cygnusx.infrastructure.database.models.chat import ChatSessionModel
        from cygnusx.infrastructure.database.session import get_session_factory

        project_id = str(model.id)

        async def _run() -> None:
            packed = 0
            try:
                async with get_session_factory()() as db:
                    result = await db.execute(
                        select(ChatSessionModel).where(
                            ChatSessionModel.project_id == project_id,
                            ChatSessionModel.mode == "studio",
                            ChatSessionModel.status != "deleted",
                        )
                    )
                    sessions = list(result.scalars().all())
                    for session in sessions:
                        try:
                            await pack_session(db, session.session_id, "system", is_admin=True)
                            packed += 1
                        except Exception as exc:  # noqa: BLE001 - busy 等跳过记日志
                            logger.info(
                                "[Archive] 项目 {} 会话 {} 完成触发打包跳过: {}",
                                model.slug,
                                session.session_id[:12],
                                exc,
                            )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Archive] 项目 {} 会话打包任务失败: {}", model.slug, exc)
            if packed:
                logger.info("[Archive] 项目 {} 完成触发打包 {} 个会话", model.slug, packed)

        # fire-and-forget：API 事务不等待打包完成
        asyncio.create_task(_run())

    async def delete_project(self, user_id: UUID, project_id: UUID) -> bool:
        """保留删除身份与物理文件，原子删除项目行及目录索引。

        科研保留引用（数据集、导入、计划、观察、下载执行、导出与项目报告）
        在任何功能开关状态下都会阻止物理删除：预检查负责给出可解释的 409，
        数据库 RESTRICT 约束兜底预检查与删除之间的并发写入；兜底触发后先
        完整回滚，再重新解释为同一业务冲突，无法识别的约束异常原样抛出。
        """
        await self._lock_owner(user_id)
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.id == project_id, ProjectModel.user_id == user_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"项目不存在：{project_id}")
        blockers = await self._retained_reference_counts(project_id)
        if blockers:
            raise self._retained_conflict(blockers)
        self._session.add(
            ProjectTombstoneModel(project_id=model.id, user_id=user_id, slug=model.slug)
        )
        await self._session.flush()
        try:
            await self._session.delete(model)
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            blockers = await self._retained_reference_counts(project_id)
            if not blockers:
                raise
            raise self._retained_conflict(blockers) from None
        # 清理目录记录
        dirs = DirectoryRepositoryImpl(self._session)
        dir_path = f"projects/{model.slug}"
        await dirs.delete(user_id, dir_path)
        await self._session.commit()
        return True

    # ------------------------------------------------------------------
    # 回填：从磁盘 projects/ 目录读取缺失项目，写入 DB
    # ------------------------------------------------------------------
    async def sync_from_disk(self, user_id: UUID) -> dict[str, int]:
        """扫描 ``users/{user_id}/projects/`` 下的一级子目录，为缺失的创建 DB 记录。

        幂等：已存在同 slug 的项目跳过。目录名即 slug，显示名暂时等于 slug
        （后续用户可通过 rename 改为可读名）。
        """
        await self._lock_owner(user_id)
        projects_root = self._factory.projects_dir(str(user_id))
        if not projects_root.exists():
            return {"created": 0, "skipped_deleted": 0}

        existing = await self._session.execute(
            select(ProjectModel.slug).where(ProjectModel.user_id == user_id)
        )
        existing_slugs = set(existing.scalars().all())
        deleted = await self._session.execute(
            select(ProjectTombstoneModel.slug).where(ProjectTombstoneModel.user_id == user_id)
        )
        deleted_slugs = set(deleted.scalars().all())
        skipped_deleted = 0

        to_insert: list[ProjectModel] = []
        for entry in projects_root.iterdir():
            if not entry.is_dir() or entry.is_symlink() or entry.name.startswith("."):
                continue
            if len(entry.name) > 200:
                continue
            if entry.name in deleted_slugs:
                skipped_deleted += 1
                continue
            if entry.name in existing_slugs:
                continue
            to_insert.append(
                ProjectModel(
                    user_id=user_id,
                    name=entry.name,
                    slug=entry.name,
                    description="",
                )
            )
        if to_insert:
            self._session.add_all(to_insert)
            from cygnusx.domain.file.entities import Directory

            directories = DirectoryRepositoryImpl(self._session)
            for project in to_insert:
                path = f"projects/{project.slug}"
                if await directories.get_by_path(user_id, path) is None:
                    await directories.save(
                        Directory(
                            id=uuid.uuid4(),
                            user_id=user_id,
                            path=path,
                            name=project.slug,
                            parent_path="projects",
                        )
                    )
            await self._session.commit()
        return {"created": len(to_insert), "skipped_deleted": skipped_deleted}

    async def _lock_owner(self, user_id: UUID) -> None:
        # All create/delete/sync operations use the same lock to reserve slug identity.
        await self._session.execute(
            select(UserModel.id).where(UserModel.id == user_id).with_for_update()
        )

    async def _find_project_by_slug(self, user_id: UUID, slug: str) -> ProjectModel | None:
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.user_id == user_id, ProjectModel.slug == slug)
        )
        return result.scalar_one_or_none()

    async def _slug_retained(self, user_id: UUID, slug: str) -> bool:
        result = await self._session.execute(
            select(ProjectTombstoneModel.project_id).where(
                ProjectTombstoneModel.user_id == user_id, ProjectTombstoneModel.slug == slug
            )
        )
        return result.scalar_one_or_none() is not None

    async def _allocate_available_slug(self, user_id: UUID, base: str) -> str:
        """在 tombstone 保留的 base slug 之外分配新的可用目录名（-2 起）。"""
        for sequence in range(2, 1000):
            candidate = f"{base}-{sequence}"
            if (
                await self._find_project_by_slug(user_id, candidate) is None
                and not await self._slug_retained(user_id, candidate)
            ):
                return candidate
        raise ConflictError("无法为该项目分配可用目录名", code="PROJECT_SLUG_EXHAUSTED")

    async def _register_project_directory(self, user_id: UUID, slug: str) -> None:
        dirs = DirectoryRepositoryImpl(self._session)
        dir_path = f"projects/{slug}"
        if await dirs.get_by_path(user_id, dir_path) is None:
            from cygnusx.domain.file.entities import Directory

            await dirs.save(
                Directory(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    path=dir_path,
                    name=slug,
                    parent_path="projects",
                )
            )

    async def _retained_reference_counts(self, project_id: UUID) -> list[tuple[str, int]]:
        counts: list[tuple[str, int]] = []
        for label, _label_zh, model in _RETAINED_REFERENCES:
            count = await self._session.scalar(
                select(func.count()).select_from(model).where(model.project_id == project_id)
            )
            if count:
                counts.append((label, int(count)))
        return counts

    @staticmethod
    def _retained_conflict(counts: list[tuple[str, int]]) -> ConflictError:
        zh = {label: label_zh for label, label_zh, _model in _RETAINED_REFERENCES}
        parts = "、".join(f"{zh.get(label, label)} {count}" for label, count in counts)
        return ConflictError(
            f"项目包含需保留的科研记录（{parts}），请先完成保留策略审核后再删除",
            code="PROJECT_HAS_RETAINED_REFERENCES",
        )

    async def capability_status(self, user_id: UUID, project_id: UUID) -> ProjectCapabilityStatus:
        project = await self._session.get(ProjectModel, project_id)
        if project is None:
            raise NotFoundError("项目不存在")
        if project.user_id != user_id:
            raise AuthorizationError("无权访问该项目")
        user = await self._session.get(UserModel, user_id, populate_existing=True)
        settings = get_settings()

        def capability(
            enabled: bool, modules: set[str], *, active: bool = True
        ) -> ProjectCapability:
            permitted = bool(
                user
                and user.status == "active"
                and active
                and (user.role == "admin" or not modules.intersection(user.disabled_modules or []))
            )
            return ProjectCapability(
                enabled=enabled,
                allowed=enabled and permitted,
                reason="SERVICE_DISABLED"
                if not enabled
                else ("AVAILABLE" if permitted else "NO_PERMISSION"),
            )

        read = settings.research_delivery_read_enabled
        return ProjectCapabilityStatus(
            research_plan=capability(settings.research_plan_enabled, {"files", "tasks", "reports"}),
            research_delivery_read=capability(read, {"files", "reports"}),
            project_export=capability(
                read and settings.project_export_enabled,
                {"files", "tasks", "reports"},
                active=project.status in {None, "active", "completed", "handed_over"},
            ),
        )
