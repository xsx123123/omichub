"""Welcome scheduling on the existing analysis queue, independent of global Beat timezone."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from celery import shared_task
from sqlalchemy import select

from cygnusx.application.services.welcome import metrics
from cygnusx.application.services.welcome.generation import generate_batch
from cygnusx.application.services.welcome.publishing import publish_due
from cygnusx.application.services.welcome.validation import Audience, week_start
from cygnusx.core.config import get_settings
from cygnusx.infrastructure.database.models.welcome import WelcomeBatchModel as Batch
from cygnusx.infrastructure.database.models.welcome import WelcomeGenerationRunModel as Run
from cygnusx.infrastructure.database.session import get_session_factory


@shared_task(
    name="welcome.generate",
    acks_late=True,
    soft_time_limit=2600,
    time_limit=2700,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
)  # type: ignore[untyped-decorator]
def generate(target_week: str, audience: Audience, revision: int = 1) -> str | None:
    result = asyncio.run(generate_batch(date.fromisoformat(target_week), audience, revision))
    return str(result) if result else None


@shared_task(name="welcome.reconcile", acks_late=True, soft_time_limit=30, time_limit=45)  # type: ignore[untyped-decorator]
def reconcile() -> dict[str, Any]:
    return asyncio.run(reconcile_async())


async def reconcile_async(now: datetime | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.welcome_enabled:
        return {"enabled": False}
    now = now or datetime.now(UTC)
    local = now.astimezone(ZoneInfo(settings.welcome_timezone))
    current = week_start(local.date())
    # Every minute repairs missed publication/restart. Generation is DB-idempotent;
    # expired running leases and bounded failed attempts are eligible for repair.
    weeks = [current]
    if local.weekday() == 6 and (local.hour, local.minute) >= (
        settings.welcome_generation_hour,
        settings.welcome_generation_minute,
    ):
        weeks.append(current + timedelta(days=7))
    pending: list[tuple[str, Audience, int]] = []
    async with get_session_factory()() as db:
        published = await publish_due(db, local.date())
        active = await db.scalars(select(Batch).where(Batch.status == "active"))
        for batch in active:
            metrics.pool_age.record(
                (local.date() - batch.week_start).days, {"audience": batch.audience}
            )
        for target in weeks:
            for audience in ("admin", "general"):
                existing = await db.scalar(
                    select(Batch)
                    .where(
                        Batch.week_start == target,
                        Batch.audience == audience,
                        Batch.locale == "zh-CN",
                    )
                    .order_by(Batch.revision.desc())
                    .limit(1)
                )
                if existing is None:
                    pending.append((target.isoformat(), audience, 1))
                    continue
                run = await db.scalar(select(Run).where(Run.batch_id == existing.id))
                if (
                    existing.status in {"failed", "generating"}
                    and run
                    and run.attempt < 3
                    and run.lease_expires_at <= now
                ):
                    pending.append((target.isoformat(), audience, existing.revision))
                elif (
                    existing.status == "generating"
                    and run
                    and run.lease_expires_at <= now
                    and run.attempt >= 3
                ):
                    existing.status = "failed"
                    run.status, run.error_code = "failed", "attempts_exhausted"
        await db.commit()
    for target_week, audience, revision in pending:
        generate.apply_async(args=[target_week, audience, revision], queue="analysis")
    return {"published": published, "enqueued": len(pending)}
