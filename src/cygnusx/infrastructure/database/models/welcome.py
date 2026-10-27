"""Offline welcome content and account-scoped delivery ledger."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cygnusx.infrastructure.database.base import Base


class WelcomeBatchModel(Base):
    __tablename__ = "welcome_batches"
    __table_args__ = (
        UniqueConstraint(
            "week_start", "audience", "locale", "revision", name="uq_welcome_batch_revision"
        ),
        CheckConstraint("audience IN ('admin','general')", name="ck_welcome_audience"),
        CheckConstraint(
            "status IN ('generating','validated','scheduled','active','retired','failed','withdrawn')",
            name="ck_welcome_batch_status",
        ),
        Index(
            "uq_welcome_one_active",
            "audience",
            "locale",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    week_start: Mapped[date] = mapped_column(Date)
    audience: Mapped[str] = mapped_column(String(24))
    locale: Mapped[str] = mapped_column(String(16), default="zh-CN")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="generating")
    agent_name: Mapped[str] = mapped_column(String(128), default="welcome_copywriter")
    prompt_version: Mapped[str] = mapped_column(String(40))
    prompt_sha256: Mapped[str] = mapped_column(String(64))
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WelcomeGenerationRunModel(Base):
    __tablename__ = "welcome_generation_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("welcome_batches.id", ondelete="CASCADE"), unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="running")
    lease_token: Mapped[UUID] = mapped_column(default=uuid4)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WelcomeMessageModel(Base):
    __tablename__ = "welcome_messages"
    __table_args__ = (
        UniqueConstraint("batch_id", "text_sha256", name="uq_welcome_message_hash"),
        Index("ix_welcome_messages_enabled", "batch_id", "enabled"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("welcome_batches.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    text_sha256: Mapped[str] = mapped_column(String(64))
    topic: Mapped[str] = mapped_column(String(32))
    tone: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text)
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("welcome_generation_runs.id"))


class WelcomeDeliveryModel(Base):
    __tablename__ = "welcome_deliveries"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="uq_welcome_user_date"),
        CheckConstraint("status IN ('reserved','shown')", name="ck_welcome_delivery_status"),
        Index("ix_welcome_deliveries_recent", "user_id", "shown_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    local_date: Mapped[date] = mapped_column(Date)
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("welcome_batches.id"))
    message_id: Mapped[UUID | None] = mapped_column(ForeignKey("welcome_messages.id"))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(20), default="reserved")
    reservation_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
