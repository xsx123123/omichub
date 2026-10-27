"""Lease-fenced offline generation; inference never holds a database transaction."""

from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from loguru import logger
from pydantic import ValidationError
from sqlalchemy import select

from cygnusx.application.services.welcome import metrics
from cygnusx.application.services.welcome.agent import WelcomeAgentAdapter, WelcomeAgentError
from cygnusx.application.services.welcome.persistence import lock_resource
from cygnusx.application.services.welcome.validation import (
    Audience,
    CopyMessage,
    CopyResponse,
    content_hash,
    reject_reason,
    topic_matches,
    week_start,
)
from cygnusx.core.config import get_settings
from cygnusx.infrastructure.database.models.welcome import WelcomeBatchModel as Batch
from cygnusx.infrastructure.database.models.welcome import WelcomeGenerationRunModel as Run
from cygnusx.infrastructure.database.models.welcome import WelcomeMessageModel as Message
from cygnusx.infrastructure.database.session import get_session_factory


async def generate_batch(
    target_week: date,
    audience: Audience,
    revision: int = 1,
) -> UUID | None:
    settings = get_settings()
    if not settings.welcome_enabled:
        return None
    if target_week != week_start(target_week) or revision < 1:
        raise ValueError("Target week must be Monday; revision must be positive")
    agent = WelcomeAgentAdapter()
    factory = get_session_factory()
    key = f"welcome:{target_week}:{audience}:zh-CN:r{revision}"
    now = datetime.now(UTC)
    calls_limit = math.ceil(settings.welcome_target_count / 8) + settings.welcome_max_retries
    lease = now + timedelta(seconds=calls_limit * settings.welcome_timeout_seconds + 60)
    async with factory() as db:
        await lock_resource(db, key)
        batch = await db.scalar(
            select(Batch).where(
                Batch.week_start == target_week,
                Batch.audience == audience,
                Batch.locale == "zh-CN",
                Batch.revision == revision,
            )
        )
        if batch is None:
            batch = Batch(
                week_start=target_week,
                audience=audience,
                revision=revision,
                prompt_version=agent.prompt_version,
                prompt_sha256=agent.prompt_hash,
            )
            db.add(batch)
            await db.flush()
            run = Run(batch_id=batch.id, idempotency_key=key, lease_expires_at=lease)
            db.add(run)
            await db.flush()
        else:
            existing_run = await db.scalar(
                select(Run).where(Run.batch_id == batch.id).with_for_update()
            )
            if existing_run is None:
                raise RuntimeError("Welcome batch has no audit run")
            run = existing_run
            # A withdrawal can commit while this retry waits for the run lock.
            # Its batch snapshot must be reloaded before deciding to reacquire.
            await db.refresh(batch)
            if run.status == "cancelled":
                return batch.id
            if batch.status != "generating" and batch.status != "failed":
                return batch.id
            if run.status == "running" and run.lease_expires_at > now:
                return batch.id
            if run.attempt >= 3:
                run.status = "failed"
                run.error_code = "attempts_exhausted"
                batch.status = "failed"
                await db.commit()
                return batch.id
            run.attempt += 1
            run.lease_token = uuid4()
            run.lease_expires_at = lease
            run.status = "running"
            batch.status = "generating"
            batch.prompt_version, batch.prompt_sha256 = agent.prompt_version, agent.prompt_hash
        batch_id, run_id, token = batch.id, run.id, run.lease_token
        history = list(
            (
                await db.scalars(
                    select(Message.text)
                    .join(Batch)
                    .where(
                        Batch.week_start >= target_week - timedelta(weeks=8),
                        Batch.week_start <= target_week,
                        Batch.id != batch_id,
                        Batch.status.in_(["validated", "scheduled", "active", "retired"]),
                        Message.enabled.is_(True),
                    )
                    .limit(1000)
                )
            ).all()
        )
        await db.commit()

    accepted: list[CopyMessage] = []
    rejected: Counter[str] = Counter()
    for position in range(calls_limit):
        if len(accepted) >= settings.welcome_target_count:
            break
        metadata: dict[str, Any] = {"position": position, "attempt": run.attempt}
        try:
            result = await agent.generate(
                audience=audience,
                target_week=target_week,
                count=min(8, settings.welcome_target_count - len(accepted)),
                recent=history + [m.text for m in accepted],
                run_id=run_id,
                focus_round=position,
            )
            metadata.update(result.metadata)
            metrics.llm_tokens.add(
                int(result.metadata.get("usage", {}).get("total_tokens", 0)), {"audience": audience}
            )
            response = CopyResponse.model_validate_json(result.text)
            for message in response.messages:
                reason = reject_reason(message.text, history + [m.text for m in accepted])
                if reason is None and not topic_matches(message):
                    reason = "topic_mismatch"
                if reason:
                    rejected[reason] += 1
                elif len(accepted) < settings.welcome_target_count:
                    accepted.append(message)
        except WelcomeAgentError as exc:
            rejected["agent_unavailable"] += 1
            metadata.update(exc.metadata)
            metadata["error_code"] = str(exc)
            metrics.llm_tokens.add(
                int(exc.metadata.get("usage", {}).get("total_tokens", 0)), {"audience": audience}
            )
        except (ValidationError, ValueError):
            rejected["invalid_schema"] += 1
            metadata["error_code"] = "invalid_schema"
        except Exception as exc:
            # Only categories are persisted: provider error text may contain credentials.
            rejected["agent_unavailable"] += 1
            metadata["error_code"] = type(exc).__name__
            logger.warning(
                "Welcome agent run {} call {} failed ({})", run_id, position, type(exc).__name__
            )
        async with factory() as db:
            current = await db.scalar(select(Run).where(Run.id == run_id).with_for_update())
            if current is None or current.lease_token != token or current.status != "running":
                return batch_id
            current.calls = [*current.calls, metadata]
            await db.commit()

    topics = sorted({m.topic for m in accepted})
    valid = len(accepted) >= settings.welcome_min_valid_count and len(topics) >= 4
    async with factory() as db:
        current = await db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if current is None or current.lease_token != token or current.status != "running":
            return batch_id
        batch = await db.get(Batch, batch_id)
        if batch is None:
            raise RuntimeError("Welcome batch disappeared")
        batch.validation_report = {
            "valid": valid,
            "valid_count": len(accepted),
            "topics": topics,
            "rejections": dict(rejected),
            "policy_version": "v2",
        }
        current.status = "succeeded" if valid else "failed"
        current.error_code = None if valid else "quality_threshold"
        current.finished_at = datetime.now(UTC)
        current.lease_expires_at = current.finished_at + timedelta(seconds=60 * 2**current.attempt)
        batch.status = (
            ("scheduled" if settings.welcome_auto_publish else "validated") if valid else "failed"
        )
        if valid:
            db.add_all(
                [
                    Message(
                        batch_id=batch_id,
                        text=m.text,
                        text_sha256=content_hash(m.text),
                        topic=m.topic,
                        tone=m.tone,
                        agent_run_id=run_id,
                    )
                    for m in accepted
                ]
            )
        await db.commit()
    metrics.generation_runs.add(
        1, {"result": "succeeded" if valid else "failed", "audience": audience}
    )
    metrics.valid_messages.record(len(accepted), {"audience": audience})
    logger.bind(
        event="welcome.generation",
        agent_run_id=str(run_id),
        valid=valid,
        valid_count=len(accepted),
        audience=audience,
    ).info("Welcome generation completed")
    return batch_id
