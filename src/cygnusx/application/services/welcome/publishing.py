"""Atomic audience-scoped publishing and explicit administrative withdrawal/rollback."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.services.welcome.persistence import lock_resource
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import BusinessError, NotFoundError
from cygnusx.infrastructure.database.models.welcome import WelcomeBatchModel as Batch
from cygnusx.infrastructure.database.models.welcome import WelcomeMessageModel as Message


async def check_quality(db: AsyncSession, batch: Batch) -> None:
    messages = list(
        (
            await db.scalars(
                select(Message).where(
                    Message.batch_id == batch.id,
                    Message.enabled.is_(True),
                )
            )
        ).all()
    )
    if (
        not batch.validation_report.get("valid")
        or len(messages) < get_settings().welcome_min_valid_count
        or len({m.topic for m in messages}) < 4
    ):
        raise BusinessError("欢迎池未达到发布质量门槛")


async def publish(
    db: AsyncSession,
    batch_id: UUID,
    today: date,
    *,
    rollback: bool = False,
    actor: UUID | None = None,
    note: str | None = None,
) -> bool:
    batch = await db.get(Batch, batch_id)
    if batch is None:
        raise NotFoundError("欢迎池不存在")
    await lock_resource(db, f"welcome:publish:{batch.audience}:{batch.locale}")
    await db.refresh(batch)
    if batch.status == "active":
        return False
    allowed = {"retired"} if rollback else {"scheduled", "validated"}
    if batch.status not in allowed or batch.week_start > today:
        raise BusinessError("欢迎池尚未到期或不可发布")
    await check_quality(db, batch)
    active = await db.scalar(
        select(Batch).where(
            Batch.audience == batch.audience,
            Batch.locale == batch.locale,
            Batch.status == "active",
        )
    )
    if active is not None:
        if not rollback and (active.week_start, active.revision) >= (
            batch.week_start,
            batch.revision,
        ):
            batch.status = "retired"
            return False
        active.status = "retired"
        await db.flush()  # Retire before activate: partial unique index is immediate.
    batch.status = "active"
    batch.activated_at = datetime.now(UTC)
    if actor is not None:
        batch.reviewed_by, batch.review_note = actor, note
    await db.flush()
    return True


async def publish_due(db: AsyncSession, today: date) -> int:
    candidates = list(
        (
            await db.scalars(
                select(Batch)
                .where(
                    Batch.status == "scheduled",
                    Batch.week_start <= today,
                )
                .order_by(
                    Batch.audience, Batch.locale, Batch.week_start.desc(), Batch.revision.desc()
                )
            )
        ).all()
    )
    count = 0
    for batch in candidates:
        # Candidate reads precede the lock and can race with an administrative
        # withdrawal or another publisher. Never turn their terminal state back
        # into a reviewable pool using a stale ORM instance.
        await lock_resource(db, f"welcome:publish:{batch.audience}:{batch.locale}")
        await db.refresh(batch)
        if batch.status != "scheduled":
            continue
        try:
            count += await publish(db, batch.id, today)
        except BusinessError:
            # Disabling copy after QA can invalidate a scheduled pool. Keep it for
            # review without preventing another audience's publication.
            batch.status = "validated"
            batch.review_note = "发布时质量门槛未满足，请人工复核"
            logger.warning("Welcome batch {} needs publication review", batch.id)
    return count


async def withdraw(db: AsyncSession, batch_id: UUID, actor: UUID, note: str) -> None:
    batch = await db.get(Batch, batch_id)
    if batch is None:
        raise NotFoundError("欢迎池不存在")
    await lock_resource(db, f"welcome:publish:{batch.audience}:{batch.locale}")
    await db.refresh(batch)
    from cygnusx.infrastructure.database.models.welcome import WelcomeGenerationRunModel as Run

    await db.scalar(select(Run).where(Run.batch_id == batch_id).with_for_update())
    batch.status = "withdrawn"
    batch.reviewed_by, batch.review_note = actor, note
    # A live generator must not resurrect a withdrawn batch after inference finishes.
    await db.execute(update(Run).where(Run.batch_id == batch_id).values(status="cancelled"))
