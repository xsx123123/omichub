"""报告中心 DTO 模型"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from cygnusx.application.schemas.base import CygnusXBaseSchema, PaginationParams


class ReportFileResponse(CygnusXBaseSchema):
    """报告文件响应"""

    id: UUID
    report_id: UUID
    name: str
    type: str
    size: int
    path: str
    is_primary: bool
    created_at: datetime
    sha256: str | None = None


class ReportResponse(CygnusXBaseSchema):
    """报告详情响应"""

    id: UUID
    task_id: UUID
    user_id: UUID
    flow_id: str
    flow_name: str
    flow_version: str
    flow_icon: str
    title: str
    description: str
    status: str
    sample_count: int
    duration: int
    created_at: datetime
    completed_at: datetime | None
    is_read: bool
    is_starred: bool
    # 版本树（OmicStudio 产物回填）：parent_id 指向被优化的原报告
    parent_id: UUID | None = None
    version: int = 1
    files: list[ReportFileResponse] = []
    report_kind: str = "scientific"
    snapshot_id: UUID | None = None
    template_version: str | None = None
    evidence_partial: bool | None = None


class ReportVersionTreeResponse(CygnusXBaseSchema):
    """同一原始报告衍生出的版本树。"""

    root_id: UUID
    current_id: UUID
    items: list[ReportResponse]


class ReportPreviewResponse(CygnusXBaseSchema):
    """Browser-bound URL; never a publicly shareable report link."""

    url: str
    expires_at: datetime
    channel: str


class ReportListResponse(CygnusXBaseSchema):
    """报告列表响应"""

    items: list[ReportResponse]
    total: int


class ReportFilterParams(PaginationParams):
    """报告列表过滤参数"""

    task_id: UUID | None = None
    keyword: str | None = None
    flow_id: str | None = None
    status: str | None = None
    date_range: str | None = None  # 7d / 30d / 90d
    is_starred: bool | None = None


class ToggleStarRequest(CygnusXBaseSchema):
    """收藏请求"""

    is_starred: bool


class ReportJobResponse(CygnusXBaseSchema):
    id: UUID
    task_id: UUID
    status: str
    template_version: str
    snapshot_id: UUID | None = None
    report_id: UUID | None = None
    error_message: str = ""
    error_code: str | None = None
    retryable: bool = False
    evidence_partial: bool = True
    finished_at: datetime | None = None
    attempt_count: int = 0
    created_at: datetime
    updated_at: datetime


class ReportSnapshotResponse(CygnusXBaseSchema):
    id: UUID
    task_id: UUID
    run_id: UUID | None = None
    schema_version: str
    snapshot_digest: str
    captured_at: datetime
    payload: dict[str, Any]
