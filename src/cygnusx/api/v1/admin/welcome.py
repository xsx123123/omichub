"""RBAC-protected welcome pool review, generation, publication and rollback."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from sqlalchemy import select

from cygnusx.api.deps import CurrentUserId, DbSession
from cygnusx.application.schemas.welcome import (
    GenerationRequest,
    MessageReviewRequest,
    ReviewRequest,
)
from cygnusx.application.services.welcome.persistence import lock_resource
from cygnusx.application.services.welcome.publishing import publish, withdraw
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import NotFoundError
from cygnusx.infrastructure.database.models.welcome import WelcomeBatchModel as Batch
from cygnusx.infrastructure.database.models.welcome import WelcomeGenerationRunModel as Run
from cygnusx.infrastructure.database.models.welcome import WelcomeMessageModel as Message
from cygnusx.middleware.rbac import AdminRequired

router = APIRouter()


def batch_dto(batch: Batch) -> dict[str, Any]:
    return {
        key: getattr(batch, key)
        for key in (
            "id",
            "week_start",
            "audience",
            "locale",
            "revision",
            "status",
            "agent_name",
            "prompt_version",
            "prompt_sha256",
            "validation_report",
            "reviewed_by",
            "review_note",
            "created_at",
            "activated_at",
        )
    }


@router.get("/batches")
async def list_batches(
    _admin: AdminRequired, db: DbSession, limit: int = Query(50, ge=1, le=100)
) -> list[dict[str, Any]]:
    rows = await db.scalars(select(Batch).order_by(Batch.created_at.desc()).limit(limit))
    return [batch_dto(row) for row in rows]


@router.get("/batches/{batch_id}")
async def detail(batch_id: UUID, _admin: AdminRequired, db: DbSession) -> dict[str, Any]:
    batch = await db.get(Batch, batch_id)
    if batch is None:
        raise NotFoundError("欢迎池不存在")
    result = batch_dto(batch)
    messages = await db.scalars(select(Message).where(Message.batch_id == batch_id))
    result["messages"] = [
        {
            key: getattr(m, key)
            for key in (
                "id",
                "text",
                "topic",
                "tone",
                "enabled",
                "disabled_reason",
                "agent_run_id",
            )
        }
        for m in messages
    ]
    run = await db.scalar(select(Run).where(Run.batch_id == batch_id))
    result["run"] = (
        {
            key: getattr(run, key)
            for key in (
                "id",
                "idempotency_key",
                "status",
                "attempt",
                "calls",
                "error_code",
                "started_at",
                "finished_at",
                "lease_expires_at",
            )
        }
        if run
        else None
    )
    return result


@router.post("/generate", status_code=202)
async def generate(req: GenerationRequest, _admin: AdminRequired) -> dict[str, str]:
    from cygnusx.infrastructure.celery_app.tasks.welcome import generate as generate_task

    task = await asyncio.to_thread(
        generate_task.apply_async,
        args=[req.target_week.isoformat(), req.audience, req.revision],
        queue="analysis",
    )
    return {"task_id": str(task.id)}


@router.post("/batches/{batch_id}/{action}")
async def review_batch(
    batch_id: UUID,
    action: str,
    req: ReviewRequest,
    _admin: AdminRequired,
    user_id: CurrentUserId,
    db: DbSession,
) -> dict[str, bool]:
    today = datetime.now(ZoneInfo(get_settings().welcome_timezone)).date()
    if action == "withdraw":
        await withdraw(db, batch_id, UUID(user_id), req.note)
    elif action in {"publish", "rollback"}:
        await publish(
            db, batch_id, today, rollback=action == "rollback", actor=UUID(user_id), note=req.note
        )
    else:
        raise NotFoundError("未知欢迎池操作")
    return {"ok": True}


@router.patch("/messages/{message_id}")
async def review_message(
    message_id: UUID,
    req: MessageReviewRequest,
    _admin: AdminRequired,
    user_id: CurrentUserId,
    db: DbSession,
) -> dict[str, bool]:
    message = await db.get(Message, message_id)
    if message is None:
        raise NotFoundError("欢迎语不存在")
    batch = await db.get(Batch, message.batch_id)
    if batch is None:
        raise NotFoundError("欢迎池不存在")
    await lock_resource(db, f"welcome:publish:{batch.audience}:{batch.locale}")
    # Compare against the post-lock state, otherwise SQLAlchemy can omit an
    # explicit restore that matches an outdated enabled=True snapshot.
    await db.refresh(message)
    await db.refresh(batch)
    message.enabled, message.disabled_reason = req.enabled, req.note
    batch.reviewed_by, batch.review_note = UUID(user_id), req.note
    return {"ok": True}
