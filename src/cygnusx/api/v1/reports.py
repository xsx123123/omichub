"""报告中心路由"""

import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from loguru import logger

from cygnusx.api.deps import CurrentJwtUserId, CurrentUserId, DbSession, oauth2_scheme
from cygnusx.application.schemas.chat import ChatStreamRequest
from cygnusx.application.schemas.report import (
    ReportFilterParams,
    ReportJobResponse,
    ReportListResponse,
    ReportPreviewResponse,
    ReportResponse,
    ReportSnapshotResponse,
    ReportVersionTreeResponse,
    ToggleStarRequest,
)
from cygnusx.application.services.report_preview_renderer import preview_csp, render_preview
from cygnusx.application.services.report_service import ReportService
from cygnusx.application.services.reproducible_report_service import ReproducibleReportService
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import AuthorizationError, CygnusXError
from cygnusx.core.report_preview import (
    PREVIEW_CONTEXT_COOKIE,
    PREVIEW_COOKIE_PATH,
    PREVIEW_SESSION_COOKIE,
    context_digest,
    sign_preview_claims,
    verify_preview_grant,
)
from cygnusx.core.security import decode_token
from cygnusx.infrastructure.config.module_registry import get_module_registry
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.middleware.module_gate import match_module_by_path

router = APIRouter()


@router.post("/{report_id}/copilot/session", summary="创建报告绑定的只读 Copilot 会话")
async def create_report_copilot_session(
    report_id: UUID, current_user_id: CurrentUserId, db: DbSession
) -> dict[str, object]:
    """Create a normal persisted chat session with a server-owned report binding."""
    from sqlalchemy import select

    from cygnusx.application.services.chat_service import ChatService
    from cygnusx.application.services.report_copilot_service import ReportCopilotService
    from cygnusx.core.exceptions import NotFoundError
    from cygnusx.infrastructure.database.models.ai_provider import AIProviderConfigModel
    from cygnusx.infrastructure.database.models.report import ReportModel

    report = await db.scalar(
        select(ReportModel).where(
            ReportModel.id == report_id, ReportModel.user_id == UUID(current_user_id)
        )
    )
    if report is None:
        raise NotFoundError("报告不存在或无权访问")
    if report.status != "completed" or report.report_kind == "delivery":
        raise HTTPException(status_code=409, detail="当前报告不可供 Copilot 解读")
    models = await db.scalars(
        select(AIProviderConfigModel)
        .where(AIProviderConfigModel.is_active.is_(True))
        .order_by(AIProviderConfigModel.is_default.desc(), AIProviderConfigModel.updated_at.desc())
    )
    model = next(
        (item for item in models if (item.extra_params or {}).get("supports_tools", True)),
        None,
    )
    if model is None:
        raise HTTPException(status_code=503, detail="当前没有可用的 AI 模型")
    service = ChatService(db)
    created = await service.create_session(
        str(current_user_id),
        model.id,
        f"报告解读：{report.title[:120]}",
        agent_id="agent-general",
        mode="chat",
        project_id=None,
        sandbox_meta={"report_copilot": {"report_id": str(report.id), "schema_version": 1}},
        require_project=False,
    )
    session = await service.get_session(created.session_id, str(current_user_id))
    if session is not None:
        # The generic session factory may attach an implicit default project. A report
        # Copilot is report scoped and must not inherit that unrelated project identity.
        session.project_id = None
        session.sandbox_meta = {
            "report_copilot": {
                "report_id": str(report.id),
                "schema_version": 1,
            }
        }
        await db.flush()
    metadata = await ReportCopilotService(db, str(current_user_id), created.session_id).metadata()
    if session is not None:
        sandbox_meta = dict(session.sandbox_meta or {})
        binding = dict(sandbox_meta.get("report_copilot") or {})
        binding["context_snapshot"] = {"schema_version": 1, **metadata}
        sandbox_meta["report_copilot"] = binding
        session.sandbox_meta = sandbox_meta
        await db.flush()
    return {
        "session_id": created.session_id,
        "model_id": str(created.model_id),
        "metadata": metadata,
        "warning": (
            (
                "该报告使用 BioReport 2.0.0 兼容降级数据；样本分组或结果表说明可能不完整。"
                if metadata.get("metadata_status") == "legacy_degraded"
                else "该报告缺少部分结构化元数据；样本分组或结果表可能无法查询。"
            )
            if metadata.get("metadata_status") != "available"
            else None
        ),
    }


@router.get("/{report_id}/copilot/session", summary="读取已绑定报告的 Copilot 上下文")
async def get_report_copilot_session(
    report_id: UUID,
    current_user_id: CurrentUserId,
    db: DbSession,
    session_id: str = Query(..., min_length=1, max_length=50),
) -> dict[str, object]:
    from sqlalchemy import select

    from cygnusx.application.services.report_copilot_service import ReportCopilotService
    from cygnusx.core.exceptions import AuthorizationError
    from cygnusx.infrastructure.database.models.chat import ChatSessionModel

    session = await db.scalar(
        select(ChatSessionModel).where(
            ChatSessionModel.session_id == session_id,
            ChatSessionModel.user_id == current_user_id,
            ChatSessionModel.status == "active",
        )
    )
    binding = (session.sandbox_meta or {}).get("report_copilot") if session else None
    if (
        session is None
        or not isinstance(binding, dict)
        or binding.get("report_id") != str(report_id)
    ):
        raise AuthorizationError("Copilot 会话与当前报告不匹配")
    metadata = await ReportCopilotService(db, str(current_user_id), session_id).metadata()
    return {
        "session_id": session_id,
        "model_id": str(session.model_id),
        "metadata": metadata,
        "warning": (
            (
                "该报告使用 BioReport 2.0.0 兼容降级数据；样本分组或结果表说明可能不完整。"
                if metadata.get("metadata_status") == "legacy_degraded"
                else "该报告缺少部分结构化元数据；样本分组或结果表可能无法查询。"
            )
            if metadata.get("metadata_status") != "available"
            else None
        ),
    }


@router.post("/{report_id}/copilot/stream", summary="报告绑定的 Copilot SSE 对话")
async def stream_report_copilot(
    report_id: UUID,
    request: ChatStreamRequest,
    current_user_id: CurrentUserId,
    db: DbSession,
) -> StreamingResponse:
    from sqlalchemy import select

    from cygnusx.application.services.chat_service import ChatService
    from cygnusx.core.exceptions import AuthorizationError
    from cygnusx.infrastructure.database.models.chat import ChatSessionModel

    if not request.session_id:
        raise HTTPException(status_code=400, detail="缺少报告 Copilot 会话")
    session = await db.scalar(
        select(ChatSessionModel).where(
            ChatSessionModel.session_id == request.session_id,
            ChatSessionModel.user_id == current_user_id,
            ChatSessionModel.status == "active",
        )
    )
    binding = (session.sandbox_meta or {}).get("report_copilot") if session else None
    if (
        session is None
        or not isinstance(binding, dict)
        or binding.get("report_id") != str(report_id)
    ):
        raise AuthorizationError("Copilot 会话与当前报告不匹配")
    safe_messages = [
        {"role": item["role"], "content": str(item.get("content") or "")[:12_000]}
        for item in request.messages[-40:]
        if isinstance(item, dict)
        and item.get("role") in {"user", "assistant"}
        and isinstance(item.get("content", ""), str)
    ]
    if not safe_messages or safe_messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="请发送一条用户问题")

    async def generate() -> AsyncIterator[str]:
        import json

        from cygnusx.api.v1.chat import _with_sse_heartbeat
        from cygnusx.application.services.chat.chat_event_service import ChatEventService

        service = ChatService(db)
        event_service = ChatEventService.from_settings()
        gen = service.stream_agent_chat(
            user_id=str(current_user_id),
            agent_id="agent-general",
            messages=safe_messages,
            session_id=request.session_id,
            model_id=session.model_id,
            attachments=[],
            enable_web_search=False,
            enable_code_execution=False,
            deep_thinking=False,
            mode="chat",
            mcp_mode="off",
            extra_mcp_servers=[],
            multi_agent=False,
            overdrive=False,
            extend_max_rounds=False,
            project_id=None,
            runtime_context={"report_copilot": True},
            auto_approve=False,
        )
        terminal_sent = False
        try:
            async for chunk in _with_sse_heartbeat(gen):
                if chunk.type == "heartbeat":
                    yield ": heartbeat\n\n"
                    continue
                chunk = event_service.before_send(chunk)
                data = {"type": chunk.type, "content": chunk.content}
                if chunk.metadata:
                    data.update(chunk.metadata)
                yield f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
                if chunk.type in {"done", "error", "agent_turn_failed"}:
                    terminal_sent = True
                if chunk.type == "done":
                    break
        except Exception as exc:  # noqa: BLE001
            logger.exception("报告 Copilot SSE 处理失败: {}", exc)
            if not terminal_sent:
                yield (
                    "data: "
                    + json.dumps(
                        {"type": "error", "content": "报告解读暂时失败，请稍后重试。"},
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
        finally:
            event_service.after_stream()
            try:
                await db.commit()
            except Exception:  # noqa: BLE001
                await db.rollback()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def get_report_service(db: DbSession) -> ReportService:
    """获取报告服务实例"""
    return ReportService(db)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


@router.get("/jobs/{job_id}", response_model=ReportJobResponse, summary="获取报告生成状态")
async def get_report_job(
    job_id: UUID, current_user_id: CurrentUserId, db: DbSession
) -> ReportJobResponse:
    return await ReproducibleReportService(db).get_job(current_user_id, job_id)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=ReportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="安全重试报告生成",
)
async def retry_report_job(
    job_id: UUID, current_user_id: CurrentUserId, db: DbSession
) -> ReportJobResponse:
    return await ReproducibleReportService(db).retry(current_user_id, job_id)


@router.get(
    "/{report_id}/snapshot",
    response_model=ReportSnapshotResponse,
    summary="获取报告证据快照",
)
async def get_report_snapshot(
    report_id: UUID, current_user_id: CurrentUserId, db: DbSession
) -> ReportSnapshotResponse:
    return await ReproducibleReportService(db).get_snapshot_for_report(current_user_id, report_id)


@router.post(
    "/{report_id}/delivery",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="生成科研交付包",
)
async def build_delivery_package(
    report_id: UUID,
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> ReportResponse:
    report = await service.build_delivery_package(report_id, current_user_id)
    return await service.get_report(report.id, current_user_id)


@router.get("", response_model=ReportListResponse, summary="获取报告列表")
async def list_reports(
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
    task_id: Annotated[UUID | None, Query(description="任务 ID")] = None,
    keyword: Annotated[str | None, Query(description="关键词搜索")] = None,
    flow_id: Annotated[str | None, Query(description="流程 ID")] = None,
    status: Annotated[str | None, Query(description="状态")] = None,
    date_range: Annotated[str | None, Query(description="时间范围: 7d/30d/90d")] = None,
    is_starred: Annotated[bool | None, Query(description="是否收藏")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="每页条数")] = 10,
) -> ReportListResponse:
    """获取当前用户的报告列表"""
    params = ReportFilterParams(
        task_id=task_id,
        keyword=keyword,
        flow_id=flow_id,
        status=status,
        date_range=date_range,
        is_starred=is_starred,
        page=page,
        page_size=page_size,
    )
    return await service.list_reports(current_user_id, params)


@router.get("/stats", summary="获取用户报告统计")
async def get_report_stats(
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> dict[str, int]:
    """获取当前用户的报告统计概览"""
    return await service.stats(current_user_id)


@router.get(
    "/{report_id}/versions",
    response_model=ReportVersionTreeResponse,
    summary="获取报告版本树",
)
async def list_report_versions(
    report_id: UUID,
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> ReportVersionTreeResponse:
    """获取原报告及其全部 Studio 衍生版本。"""
    return await service.list_versions(report_id, current_user_id)


@router.get("/{report_id}", response_model=ReportResponse, summary="获取报告详情")
async def get_report(
    report_id: UUID,
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> ReportResponse:
    """获取指定报告详情"""
    return await service.get_report(report_id, current_user_id)


@router.get(
    "/{report_id}/preview",
    response_class=PlainTextResponse,
    summary="预览报告 HTML",
)
async def preview_report(
    report_id: UUID,
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> str:
    """获取报告 HTML 内容，用于 iframe 预览"""
    return await service.preview_html(report_id, current_user_id)


@router.get("/{report_id}/preview-url", response_model=ReportPreviewResponse)
async def get_report_preview_url(
    report_id: UUID,
    request: Request,
    response: Response,
    current_user_id: CurrentJwtUserId,
    service: ReportServiceDep,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> ReportPreviewResponse:
    """Issue a report-only URL, never a raw access token or public S3 URL."""
    await service.preview_html(report_id, current_user_id, strict=True)
    payload = decode_token(token or "")
    if not payload or payload.get("type") != "access" or payload.get("sub") != current_user_id:
        raise AuthorizationError("请登录后查看报告")
    binding = context_digest(request.cookies.get(PREVIEW_CONTEXT_COOKIE, ""))
    now = datetime.now(UTC).timestamp()
    expires = min(int(payload["exp"]), int(now) + get_settings().report_preview_ttl_seconds)
    identity = {
        "sub": current_user_id,
        "token_version": payload.get("token_version"),
        "binding": binding,
        "exp": expires,
    }
    session = sign_preview_claims({**identity, "type": "report_preview_session"})
    channel = secrets.token_hex(16)
    grant = sign_preview_claims(
        {
            **identity,
            "type": "report_preview",
            "report_id": str(report_id),
            "channel": channel,
        }
    )
    response.set_cookie(
        PREVIEW_SESSION_COOKIE,
        session,
        max_age=max(0, expires - int(now)),
        path=PREVIEW_COOKIE_PATH,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return ReportPreviewResponse(
        url=f"/api/v1/reports/{report_id}/preview-content?token={grant}",
        expires_at=datetime.fromtimestamp(expires, UTC),
        channel=channel,
    )


@router.get("/{report_id}/preview-content", response_class=HTMLResponse)
async def report_preview_content(
    report_id: UUID,
    request: Request,
    db: DbSession,
    service: ReportServiceDep,
    token: str = "",
) -> HTMLResponse:
    """Self-authenticated HTML route: both browser proof and live authorization required."""
    grant = verify_preview_grant(
        report_id,
        token,
        request.cookies.get(PREVIEW_SESSION_COOKIE, ""),
        request.cookies.get(PREVIEW_CONTEXT_COOKIE, ""),
    )
    user = await db.get(UserModel, UUID(grant["sub"]))
    if user is None or user.status != "active" or user.token_version != grant["token_version"]:
        raise AuthorizationError("报告预览登录状态已失效")
    module = match_module_by_path(request.url.path, get_module_registry().lockable_modules())
    if module and user.role != "admin" and module.key in (user.disabled_modules or []):
        raise AuthorizationError("该模块未开通", code="MODULE_LOCKED")
    request.state.user_id = str(user.id)
    status_code = 200
    try:
        detail = await service.get_report(report_id, str(user.id))
        content = await service.preview_html(report_id, str(user.id), strict=True)
        rendered = render_preview(
            report_id,
            grant["channel"],
            content=content,
            interactive=detail.report_kind == "scientific",
        )
    except CygnusXError as exc:
        status_code = exc.status_code
        rendered = render_preview(report_id, grant["channel"], error_status=status_code)
    return HTMLResponse(
        rendered,
        status_code=status_code,
        headers={
            "Content-Security-Policy": preview_csp(),
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
        },
    )


@router.get(
    "/{report_id}/files/{file_id}/download",
    summary="下载报告文件",
)
async def download_report_file(
    report_id: UUID,
    file_id: UUID,
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> Response:
    """下载报告关联文件"""
    detail = await service.get_report(report_id, current_user_id)
    if detail.report_kind in {"reproducibility", "delivery"} or service._backend.name != "local":
        content, name = await service.object_download(report_id, file_id, current_user_id)
        return Response(
            content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, safe='')}",
                "X-Content-Type-Options": "nosniff",
            },
        )
    path = await service.download_file(report_id, file_id, current_user_id)
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/octet-stream",
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除报告")
async def delete_report(
    report_id: UUID,
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> None:
    """删除报告记录（不删除底层文件）"""
    await service.delete_report(report_id, current_user_id)


@router.patch("/{report_id}/star", response_model=ReportResponse, summary="收藏/取消收藏报告")
async def toggle_star(
    report_id: UUID,
    req: ToggleStarRequest,
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> ReportResponse:
    """切换报告收藏状态"""
    return await service.toggle_star(report_id, current_user_id, req.is_starred)


@router.patch("/{report_id}/read", response_model=ReportResponse, summary="标记报告已读")
async def mark_read(
    report_id: UUID,
    current_user_id: CurrentUserId,
    service: ReportServiceDep,
) -> ReportResponse:
    """标记报告为已读"""
    return await service.mark_read(report_id, current_user_id)
