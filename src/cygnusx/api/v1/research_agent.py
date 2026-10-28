"""科研寻宝鼠原生只读发现 API。

浏览器只接触本路由；Node/TS Agent 不作为公开认证入口。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from cygnusx.api.deps import CurrentUserId, DbSession
from cygnusx.application.schemas.research_agent import (
    ResearchAgentCapabilities,
    ResearchAgentMessageRequest,
    ResearchAgentSessionCreate,
    ResearchLiteratureRequest,
    ResearchSessionUpdate,
)
from cygnusx.application.schemas.research_stats import (
    ResearchLeaderboard,
    ResearchNicknameUpdate,
    ResearchUsageStats,
)
from cygnusx.application.services.research_stats_service import ResearchStatsService
from cygnusx.application.services.research_treasure_service import ResearchTreasureService

router = APIRouter()


@router.get("/leaderboard", response_model=ResearchLeaderboard)
async def leaderboard(
    current_user_id: CurrentUserId, db: DbSession, period: Literal["all", "week"] = "all",
) -> ResearchLeaderboard:
    return await ResearchStatsService(db).leaderboard(current_user_id, period)


@router.get("/stats", response_model=ResearchUsageStats)
async def usage_stats(current_user_id: CurrentUserId, db: DbSession) -> ResearchUsageStats:
    return await ResearchStatsService(db).usage(current_user_id)


@router.patch("/nickname")
async def update_nickname(
    request: ResearchNicknameUpdate, current_user_id: CurrentUserId, db: DbSession,
) -> dict[str, object]:
    return await ResearchStatsService(db).set_nickname(current_user_id, request.nickname)


def _service(db: DbSession) -> ResearchTreasureService:
    return ResearchTreasureService(db)


@router.get("/capabilities", response_model=ResearchAgentCapabilities)
async def capabilities(user: CurrentUserId, db: DbSession) -> ResearchAgentCapabilities:
    return await _service(db).capabilities(user)


@router.post("/sessions")
async def create_session(
    request: ResearchAgentSessionCreate,
    current_user_id: CurrentUserId,
    db: DbSession,
) -> object:
    service = _service(db)
    await service.ensure_access(current_user_id)
    return await service.create_session(
        current_user_id,
        str(request.project_id) if request.project_id else None,
        request.title,
        request.model_id,
    )


@router.get("/sessions")
async def list_sessions(
    current_user_id: CurrentUserId,
    db: DbSession,
    project_id: UUID | None = None,
) -> list[object]:
    service = _service(db)
    await service.ensure_access(current_user_id)
    return await service.list_sessions(current_user_id, str(project_id) if project_id else None)


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, current_user_id: CurrentUserId, db: DbSession) -> list[object]:
    service = _service(db)
    await service.ensure_access(current_user_id)
    return await service.messages(current_user_id, session_id)


@router.post("/sessions/{session_id}/messages:stream")
async def stream_message(
    session_id: str,
    request: ResearchAgentMessageRequest,
    current_user_id: CurrentUserId,
    db: DbSession,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    service = _service(db)
    cursor = 0
    if last_event_id is not None:
        try:
            cursor = int(last_event_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Last-Event-ID") from exc
        if cursor < 0 or cursor > 2_147_483_647:
            raise HTTPException(status_code=400, detail="Invalid Last-Event-ID")
    # Check ownership before committing SSE headers so HTTP failures stay diagnosable.
    await service.check_stream_access(
        current_user_id, session_id, request.model_id, request.request_id,
        request.content, request.lang,
    )
    await service.ensure_generation_running(
        current_user_id,
        session_id,
        request.content,
        request.model_id,
        request.lang,
        request.request_id,
    )

    async def generate() -> AsyncIterator[str]:
        async for event in service.stream_message(
            current_user_id,
            session_id,
            request.content,
            request.model_id,
            request.lang,
            request.request_id,
            cursor,
        ):
            event_id = event.pop("_sse_id")
            yield f"id: {event_id}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str, current_user_id: CurrentUserId, db: DbSession) -> dict[str, str]:
    service = _service(db)
    await service.ensure_access(current_user_id)
    return {"status": await service.cancel(current_user_id, session_id)}


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str, request: ResearchSessionUpdate,
    current_user_id: CurrentUserId, db: DbSession,
) -> object:
    return await _service(db).update_session(
        current_user_id, session_id, title=request.title, status=request.status,
    )


@router.post("/sessions/{session_id}/literature")
async def literature(
    session_id: str, request: ResearchLiteratureRequest,
    current_user_id: CurrentUserId, db: DbSession,
) -> dict[str, object]:
    return await _service(db).literature(current_user_id, session_id, request.kind, request.id)
