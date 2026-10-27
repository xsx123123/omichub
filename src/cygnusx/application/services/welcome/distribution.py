"""Database-only daily claims. No generation, Redis, filesystem or model dependencies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.services.welcome import metrics
from cygnusx.application.services.welcome.persistence import lock_resource
from cygnusx.application.services.welcome.validation import FALLBACK_TEXT, week_start
from cygnusx.core.config import get_settings
from cygnusx.domain.user.value_objects import Role
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.database.models.welcome import WelcomeBatchModel as Batch
from cygnusx.infrastructure.database.models.welcome import WelcomeDeliveryModel as Delivery
from cygnusx.infrastructure.database.models.welcome import WelcomeMessageModel as Message


async def claim(
    db: AsyncSession, user_id: UUID, *, first_session: bool = False, now: datetime | None = None
) -> Delivery | None:
    settings = get_settings()
    if not settings.welcome_enabled or first_session:
        return None
    user = await db.get(UserModel, user_id)
    if user is None or user.status != "active" or user.last_login_at is None:
        return None
    audience = "admin" if user.role == Role.ADMIN.value else "general"
    if (
        audience == "general"
        and not settings.welcome_general_enabled
        and str(user_id) not in settings.welcome_general_allowlist
    ):
        return None
    now = now or datetime.now(UTC)
    today = now.astimezone(ZoneInfo(settings.welcome_timezone)).date()
    await lock_resource(db, f"welcome:claim:{user_id}:{today}")
    delivery = await db.scalar(
        select(Delivery)
        .where(
            Delivery.user_id == user_id,
            Delivery.local_date == today,
        )
        .with_for_update()
    )
    if delivery is not None and (
        delivery.status == "shown" or delivery.reservation_expires_at > now
    ):
        return None  # Concurrent tabs must not both display the same reservation.
    current_week = week_start(today)
    batch = await db.scalar(
        select(Batch)
        .where(
            Batch.audience == audience,
            Batch.locale == "zh-CN",
            Batch.status.in_(["active", "retired"]),
            Batch.validation_report["valid"].as_boolean().is_(True),
            select(Message.id)
            .where(Message.batch_id == Batch.id, Message.enabled.is_(True))
            .exists(),
            Batch.week_start <= current_week,
            Batch.week_start
            >= current_week - timedelta(days=settings.welcome_previous_pool_age_days),
        )
        .order_by((Batch.status == "active").desc(), Batch.week_start.desc(), Batch.revision.desc())
        .limit(1)
    )
    if batch:
        metrics.pool_age.record((today - batch.week_start).days, {"audience": audience})
    message = None
    if batch is not None:
        seen = select(Delivery.message_id).where(
            Delivery.user_id == user_id,
            Delivery.status == "shown",
            Delivery.local_date >= today - timedelta(days=30),
            Delivery.message_id.is_not(None),
        )
        base = select(Message).where(Message.batch_id == batch.id, Message.enabled.is_(True))
        message = await db.scalar(
            base.where(Message.id.not_in(seen)).order_by(func.random()).limit(1)
        )
        if message is None:
            message = await db.scalar(base.order_by(func.random()).limit(1))
    if delivery is None:
        delivery = Delivery(user_id=user_id, local_date=today)
        db.add(delivery)
    else:
        delivery.id = uuid4()  # Fence stale receipts from an expired reservation.
    delivery.batch_id = batch.id if message is not None and batch else None
    delivery.message_id = message.id if message else None
    delivery.text = message.text if message else FALLBACK_TEXT
    delivery.source = (
        (
            "agent_pool"
            if batch and batch.week_start == current_week and batch.status == "active"
            else "previous_pool"
        )
        if message
        else "static_fallback"
    )
    if delivery.source != "agent_pool":
        metrics.fallbacks.add(1, {"source": delivery.source, "audience": audience})
    delivery.status = "reserved"
    delivery.reservation_expires_at = now + timedelta(seconds=settings.welcome_reservation_seconds)
    await db.flush()
    return delivery


async def impression(
    db: AsyncSession, user_id: UUID, delivery_id: UUID, now: datetime | None = None
) -> bool:
    now = now or datetime.now(UTC)
    delivery = await db.scalar(
        select(Delivery)
        .where(
            Delivery.id == delivery_id,
            Delivery.user_id == user_id,
        )
        .with_for_update()
    )
    if delivery is None:
        return False
    if delivery.status == "shown":
        return True
    if delivery.reservation_expires_at <= now:
        return False
    delivery.status, delivery.shown_at = "shown", now
    metrics.impressions.add(1, {"source": delivery.source})
    return True
