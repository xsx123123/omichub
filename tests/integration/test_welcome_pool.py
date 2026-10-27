"""Real PostgreSQL concurrency and Agent graph tests. Requires an isolated migrated DB.

WELCOME_TEST_DATABASE_URL must point to a dedicated database whose name contains welcome_test.
Only welcome tables and test-created users/providers are modified. Model stream is simulated.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cygnusx.api.deps import get_current_user_id, get_db
from cygnusx.api.v1 import welcome as welcome_api
from cygnusx.api.v1.admin import welcome as admin_api
from cygnusx.application.services.welcome import agent, distribution, generation, publishing
from cygnusx.core.config import get_settings
from cygnusx.core.security import create_access_token
from cygnusx.domain.ai_provider.entities import AIProviderConfig
from cygnusx.infrastructure.ai_provider.openai_compatible import ChatChunk, provider_manager
from cygnusx.infrastructure.celery_app.tasks import welcome as tasks
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.database.models.welcome import WelcomeBatchModel as Batch
from cygnusx.infrastructure.database.models.welcome import WelcomeDeliveryModel as Delivery
from cygnusx.infrastructure.database.models.welcome import WelcomeGenerationRunModel as Run
from cygnusx.infrastructure.database.models.welcome import WelcomeMessageModel as Message

pytestmark = pytest.mark.integration

# Synthetic provider output for deterministic failure/concurrency tests, not a production seed.
COPY = [
    "从数据走向发现，让每一步分析都有迹可循。",
    "欢迎回来，愿每一次探索都有清晰的证据。",
    "复杂的科学问题，值得耐心拆解与认真思考。",
    "把灵感记下来，也给意外的发现留一点空间。",
    "一份严谨的记录，是未来复现时可靠的路标。",
    "细致维护的流程，是安静守护科研的力量。",
    "在纷繁的数据之中，寻找那个值得追问的线索。",
    "从一个小小的疑问开始，拓展认知的边界。",
    "让忙碌暂缓片刻，给科学问题一份专注。",
    "重看实验的每个细节，也许就有新的理解。",
    "把假设与事实分开，让结论多一分可信。",
    "那些不起眼的异常，也值得一次认真核对。",
    "清晰的分析思路，让团队交流更加从容。",
    "好的问题总有力量，带着好奇继续向前。",
    "留住关键参数，为后来者点亮复现的路径。",
    "稳妥的质量检查，为漫长探索积累信任。",
    "给不同的解释留位置，让科学讨论走得更深一些。",
    "在反复比较之中，磨炼面对不确定性的耐心。",
    "科研路上的小进展，也值得被伙伴们仔细珍藏。",
    "整理思绪再出发，让繁杂的任务逐渐清晰。",
    "面对新线索，带上审慎，也保留探索的热情。",
    "每个可追溯的步骤，都为共同协作添一份安心。",
    "循着问题的脉络前行，让观察与思考相遇。",
    "珍惜独立复核的机会，可靠的知识由此积累。",
]


@pytest.fixture
async def pool(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[dict[str, Any]]:
    url = os.getenv("WELCOME_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("WELCOME_TEST_DATABASE_URL not configured")
    if "welcome_test" not in url.rsplit("/", 1)[-1]:
        raise ValueError("Refusing non-isolated welcome database")
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE welcome_deliveries, welcome_messages, welcome_generation_runs, welcome_batches CASCADE"
            )
        )
    settings = get_settings().model_copy(
        update={
            "welcome_enabled": True,
            "welcome_general_enabled": False,
            "welcome_general_allowlist": [],
            "welcome_auto_publish": True,
        }
    )
    for module in (agent, generation, distribution, publishing, tasks, admin_api):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    for module in (agent, generation, tasks):
        monkeypatch.setattr(module, "get_session_factory", lambda: factory)
    provider = AIProviderConfig(
        id=uuid4(),
        name="test-provider",
        model="test-model",
        api_key="test-only",
        input_price=1.0,
        output_price=1.0,
    )
    monkeypatch.setattr(
        agent.AIProviderConfigService, "get_active_default", AsyncMock(return_value=provider)
    )
    calls: list[dict[str, Any]] = []

    async def stream(**kwargs: Any) -> AsyncIterator[ChatChunk]:
        assert not kwargs.get("tools"), "Internal agent leaked tool capabilities"
        calls.append(kwargs)
        # Repeat test corpus across audiences; duplicate policy is scoped by prior published batches.
        offset = ((len(calls) - 1) % 3) * 8
        output = [
            {
                "text": value,
                "tone": "warm",
                "topic": [
                    "discovery",
                    "evidence",
                    "research",
                    "discovery",
                    "evidence",
                    "workflow",
                    "discovery",
                    "research",
                    "general",
                    "research",
                    "research",
                    "evidence",
                    "general",
                    "research",
                    "evidence",
                    "evidence",
                    "research",
                    "general",
                    "general",
                    "workflow",
                    "discovery",
                    "evidence",
                    "research",
                    "evidence",
                ][offset + i],
            }
            for i, value in enumerate(COPY[offset : offset + 8])
        ]
        yield ChatChunk(
            type="text",
            content=json.dumps({"schema_version": "1.0", "messages": output}, ensure_ascii=False),
        )
        yield ChatChunk(
            type="done",
            metadata={
                "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
            },
        )

    monkeypatch.setattr(provider_manager, "chat_stream", stream)
    users = [uuid4(), uuid4(), uuid4()]
    async with factory() as db:
        for index, uid in enumerate(users):
            db.add(
                UserModel(
                    id=uid,
                    username=f"welcome-{uid}",
                    email=f"{uid}@example.test",
                    hashed_password="unused",
                    role="admin" if index < 2 else "user",
                    status="active",
                    last_login_at=datetime.now(UTC),
                )
            )
        await db.commit()
    yield {"factory": factory, "users": users, "settings": settings, "calls": calls}
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE welcome_deliveries, welcome_messages, welcome_generation_runs, welcome_batches CASCADE"
            )
        )
        for uid in users:
            await conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
    await engine.dispose()


async def generate_and_publish(
    pool: dict[str, Any], audience: str = "admin", revision: int = 1
) -> UUID:
    bid = await generation.generate_batch(date(2026, 10, 26), audience, revision)  # type: ignore[arg-type]
    assert bid
    async with pool["factory"]() as db:
        batch = await db.get(Batch, bid)
        assert batch.status == "scheduled", batch.validation_report
        await publishing.publish(db, bid, date(2026, 10, 26))
        await db.commit()
    return bid


async def test_graph_generation_audit_and_concurrent_daily_claims(pool: dict[str, Any]) -> None:
    factory, users = pool["factory"], pool["users"]
    bid = await generate_and_publish(pool)
    assert len(pool["calls"]) == 3
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(Message)) == 24
        run = await db.scalar(select(Run))
        assert run.status == "succeeded" and len(run.calls) == 3
        assert sum(c["usage"]["total_tokens"] for c in run.calls) == 900
        assert run.calls[0]["model_id"] == "test-model"
        assert await generation.generate_batch(date(2026, 10, 26), "admin") == bid
        assert len(pool["calls"]) == 3
    now = datetime(2026, 10, 26, 8, tzinfo=UTC)

    async def request(uid: UUID) -> Delivery | None:
        async with factory() as db:
            result = await distribution.claim(db, uid, now=now)
            await db.commit()
            return result

    claims = await asyncio.gather(*(request(users[0]) for _ in range(12)))
    shown = [c for c in claims if c]
    assert len(shown) == 1
    assert shown[0].source == "agent_pool"
    assert await request(users[1])  # Independent account has its own allowance.
    assert await request(users[2]) is None  # General rollout is off.
    async with factory() as db:
        assert not await distribution.impression(db, users[1], shown[0].id, now)
        assert await distribution.impression(db, users[0], shown[0].id, now)
        assert await distribution.impression(db, users[0], shown[0].id, now)
        await db.commit()
    assert await request(users[0]) is None
    async with factory() as db:
        tomorrow = await distribution.claim(db, users[0], now=now + timedelta(days=1))
        assert tomorrow and tomorrow.message_id != shown[0].message_id
    assert len(pool["calls"]) == 3, "Display path called model"


async def test_first_session_expiry_general_and_fallback(pool: dict[str, Any]) -> None:
    factory, users = pool["factory"], pool["users"]
    now = datetime(2026, 10, 26, 8, tzinfo=UTC)
    async with factory() as db:
        assert await distribution.claim(db, users[0], first_session=True, now=now) is None
        old = await distribution.claim(db, users[0], now=now)
        assert old and old.source == "static_fallback" and "root" not in old.text
        old_id = old.id
        await db.commit()
    async with factory() as db:
        recovered = await distribution.claim(db, users[0], now=now + timedelta(minutes=6))
        assert recovered and recovered.id != old_id
        assert not await distribution.impression(db, users[0], old_id, now + timedelta(minutes=6))
        await db.commit()
    pool["settings"].welcome_general_enabled = True
    await generate_and_publish(pool, "general")
    async with factory() as db:
        item = await distribution.claim(db, users[2], now=now)
        assert item and item.source == "agent_pool"


async def test_failed_generation_preserves_active_and_publish_rollback(
    pool: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = pool["factory"]
    old = await generate_and_publish(pool)
    # A new revision with a genuinely different approved corpus is represented by existing
    # validated messages copied for the publication-only test, not by claiming a model call.
    async with factory() as db:
        original = await db.get(Batch, old)
        candidate = Batch(
            week_start=date(2026, 10, 26),
            audience="admin",
            revision=2,
            status="scheduled",
            prompt_version=original.prompt_version,
            prompt_sha256=original.prompt_sha256,
            validation_report=original.validation_report,
        )
        db.add(candidate)
        await db.flush()
        originals = list((await db.scalars(select(Message).where(Message.batch_id == old))).all())
        for m in originals:
            db.add(
                Message(
                    batch_id=candidate.id,
                    text=m.text,
                    text_sha256=m.text_sha256,
                    topic=m.topic,
                    tone=m.tone,
                    agent_run_id=m.agent_run_id,
                )
            )
        new_id = candidate.id
        await db.commit()

    async def activate() -> bool:
        async with factory() as db:
            result = await publishing.publish(db, new_id, date(2026, 10, 26))
            await db.commit()
            return result

    assert sum(await asyncio.gather(activate(), activate())) == 1
    async with factory() as db:
        assert (
            await db.scalar(select(func.count()).select_from(Batch).where(Batch.status == "active"))
            == 1
        )
        await publishing.publish(
            db, old, date(2026, 10, 26), rollback=True, actor=pool["users"][0], note="test rollback"
        )
        await db.commit()

    async def invalid(**kwargs: Any) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(type="text", content='{"schema_version":"1.0","messages":[]}')

    monkeypatch.setattr(provider_manager, "chat_stream", invalid)
    failed = await generation.generate_batch(date(2026, 11, 2), "admin")
    async with factory() as db:
        assert (await db.get(Batch, failed)).status == "failed"
        assert (await db.get(Batch, old)).status == "active"
        await publishing.withdraw(db, old, pool["users"][0], "withdraw")
        await db.commit()
        assert (await db.get(Batch, old)).status == "withdrawn"


async def test_live_lease_duplicate_and_expired_recovery(
    pool: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = asyncio.Event()
    entered = asyncio.Event()
    original = provider_manager.chat_stream

    async def blocked(**kwargs: Any) -> AsyncIterator[ChatChunk]:
        entered.set()
        await gate.wait()
        async for chunk in original(**kwargs):
            yield chunk

    monkeypatch.setattr(provider_manager, "chat_stream", blocked)
    job = asyncio.create_task(generation.generate_batch(date(2026, 10, 26), "admin"))
    await asyncio.wait_for(entered.wait(), 10)
    bid = await generation.generate_batch(date(2026, 10, 26), "admin")
    async with pool["factory"]() as db:
        assert await db.scalar(select(func.count()).select_from(Batch)) == 1
        assert (await db.get(Batch, bid)).status == "generating"
    gate.set()
    assert await job == bid
    async with pool["factory"]() as db:
        assert await db.scalar(select(func.count()).select_from(Message)) == 24


async def test_scheduler_next_week_and_reconcile_publish(
    pool: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = []
    monkeypatch.setattr(tasks.generate, "apply_async", lambda **kw: sent.append(kw))
    result = await tasks.reconcile_async(
        datetime(2027, 1, 2, 19, tzinfo=UTC)
    )  # Sunday 03:00 Shanghai
    assert result["enqueued"] == 4
    assert {item["args"][0] for item in sent} == {"2026-12-28", "2027-01-04"}
    assert all(item["queue"] == "analysis" for item in sent)
    bid = await generation.generate_batch(date(2026, 10, 26), "admin")
    await tasks.reconcile_async(datetime(2026, 10, 26, 0, tzinfo=UTC))
    async with pool["factory"]() as db:
        assert (await db.get(Batch, bid)).status == "active"


async def test_api_rbac_signed_onboarding_receipts_and_db_failure(
    pool: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    app = FastAPI()
    from cygnusx.core.exceptions import CygnusXError
    from cygnusx.main import app as platform_app

    app.add_exception_handler(CygnusXError, platform_app.exception_handlers[CygnusXError])
    app.include_router(welcome_api.router, prefix="/welcome")
    app.include_router(admin_api.router, prefix="/admin/welcome")
    user = pool["users"][0]

    async def uid() -> str:
        return str(user)

    async def database() -> AsyncIterator[Any]:
        async with pool["factory"]() as db:
            yield db
            await db.commit()

    app.dependency_overrides[get_current_user_id] = uid
    app.dependency_overrides[get_db] = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = create_access_token(str(user), token_version=0, onboarding_session=True)
        assert (
            await client.post(
                "/welcome/claim", json={}, headers={"Authorization": f"Bearer {token}"}
            )
        ).status_code == 204
        response = await client.post("/welcome/claim", json={})
        assert response.status_code == 200
        did = response.json()["delivery_id"]
        assert (await client.post("/welcome/impression", json={"delivery_id": did})).json()[
            "accepted"
        ]
        assert (await client.post("/welcome/claim", json={})).status_code == 204
        user = pool["users"][2]
        assert (await client.get("/admin/welcome/batches")).status_code == 403
        from sqlalchemy.exc import SQLAlchemyError

        monkeypatch.setattr(
            welcome_api, "claim", AsyncMock(side_effect=SQLAlchemyError("simulated DB outage"))
        )
        assert (await client.post("/welcome/claim", json={})).status_code == 204


async def test_expired_lease_fences_stale_generator(
    pool: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    original = provider_manager.chat_stream
    first = True

    async def paused(**kwargs: Any) -> AsyncIterator[ChatChunk]:
        nonlocal first
        if first:
            first = False
            entered.set()
            await release.wait()
        async for chunk in original(**kwargs):
            yield chunk

    monkeypatch.setattr(provider_manager, "chat_stream", paused)
    stale = asyncio.create_task(generation.generate_batch(date(2026, 10, 26), "admin"))
    await asyncio.wait_for(entered.wait(), 10)
    async with pool["factory"]() as db:
        run = await db.scalar(select(Run))
        run.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    fresh = await generation.generate_batch(date(2026, 10, 26), "admin")
    release.set()
    assert await stale == fresh
    async with pool["factory"]() as db:
        assert await db.scalar(select(func.count()).select_from(Message)) == 24
        run = await db.scalar(select(Run))
        assert run.attempt == 2 and len(run.calls) == 3 and run.status == "succeeded"


async def test_timeout_and_unrequested_tools_cannot_execute(
    pool: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = agent.WelcomeAgentAdapter()
    pool["settings"].welcome_timeout_seconds = 0.01

    async def slow(**kwargs: Any) -> AsyncIterator[ChatChunk]:
        await asyncio.Event().wait()
        yield ChatChunk(type="text", content="unreachable")

    monkeypatch.setattr(provider_manager, "chat_stream", slow)
    with pytest.raises(agent.WelcomeAgentError, match="TimeoutError"):
        await adapter.generate(
            audience="admin", target_week=date(2026, 10, 26), count=8, recent=[], run_id=uuid4()
        )
    pool["settings"].welcome_timeout_seconds = 180

    async def tools(**kwargs: Any) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(
            type="tool_calls",
            metadata={
                "tool_calls": [{"id": "bad", "function": {"name": "shell", "arguments": "{}"}}]
            },
        )

    monkeypatch.setattr(provider_manager, "chat_stream", tools)
    with pytest.raises(RuntimeError, match="welcome_agent_execution_failed"):
        await adapter.generate(
            audience="admin", target_week=date(2026, 10, 26), count=8, recent=[], run_id=uuid4()
        )


async def test_previous_pool_age_and_disabled_messages(pool: dict[str, Any]) -> None:
    bid = await generate_and_publish(pool)
    async with pool["factory"]() as db:
        first = await db.scalar(select(Message).where(Message.batch_id == bid))
        first.enabled = False
        await db.commit()
    async with pool["factory"]() as db:
        previous = await distribution.claim(
            db, pool["users"][0], now=datetime(2026, 11, 2, 8, tzinfo=UTC)
        )
        assert previous and previous.source == "previous_pool" and previous.message_id != first.id
        old = await distribution.claim(
            db, pool["users"][1], now=datetime(2026, 11, 9, 8, tzinfo=UTC)
        )
        assert old and old.source == "static_fallback"


async def test_publication_transaction_failure_preserves_old_pool(pool: dict[str, Any]) -> None:
    old_id = await generate_and_publish(pool)
    factory = pool["factory"]
    async with factory() as db:
        old = await db.get(Batch, old_id)
        new = Batch(
            week_start=old.week_start,
            audience=old.audience,
            revision=2,
            status="scheduled",
            prompt_version=old.prompt_version,
            prompt_sha256=old.prompt_sha256,
            validation_report=old.validation_report,
        )
        db.add(new)
        await db.flush()
        originals = list(
            (await db.scalars(select(Message).where(Message.batch_id == old_id))).all()
        )
        for message in originals:
            db.add(
                Message(
                    batch_id=new.id,
                    text=message.text,
                    text_sha256=message.text_sha256,
                    topic=message.topic,
                    tone=message.tone,
                    agent_run_id=message.agent_run_id,
                )
            )
        new_id = new.id
        await db.commit()
    from sqlalchemy.exc import DBAPIError

    async with factory() as db:
        await publishing.publish(db, new_id, date(2026, 10, 26))
        with pytest.raises(DBAPIError):
            await db.execute(text("SELECT 1 / 0"))
        await db.rollback()
    async with factory() as db:
        assert (await db.get(Batch, old_id)).status == "active"
        assert (await db.get(Batch, new_id)).status == "scheduled"
        assert await publishing.publish_due(db, date(2026, 10, 26)) == 1
        await db.commit()
        assert (await db.get(Batch, new_id)).status == "active"

    async with factory() as db:
        from sqlalchemy import update

        await db.execute(update(Message).where(Message.batch_id == new_id).values(enabled=False))
        await db.commit()
    async with factory() as db:
        item = await distribution.claim(
            db, pool["users"][1], now=datetime(2026, 10, 26, 8, tzinfo=UTC)
        )
        assert item and item.batch_id == old_id and item.source == "previous_pool"


async def test_due_publication_does_not_undo_concurrent_withdrawal(
    pool: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bid = await generation.generate_batch(date(2026, 10, 26), "admin")
    selected, release = asyncio.Event(), asyncio.Event()
    real_lock = publishing.lock_resource
    async with pool["factory"]() as pending_db:

        async def pause_after_candidate_read(db: Any, key: str) -> None:
            if db is pending_db and not selected.is_set():
                selected.set()
                await release.wait()
            await real_lock(db, key)

        monkeypatch.setattr(publishing, "lock_resource", pause_after_candidate_read)
        pending = asyncio.create_task(publishing.publish_due(pending_db, date(2026, 10, 26)))
        await asyncio.wait_for(selected.wait(), 10)
        async with pool["factory"]() as db:
            await publishing.withdraw(db, bid, pool["users"][0], "withdraw before publication")
            await db.commit()
        release.set()
        assert await pending == 0
        await pending_db.commit()
    async with pool["factory"]() as db:
        assert (await db.get(Batch, bid)).status == "withdrawn"
        assert (await db.scalar(select(Run).where(Run.batch_id == bid))).status == "cancelled"


async def test_generation_retry_does_not_undo_concurrent_withdrawal(
    pool: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_stream = provider_manager.chat_stream

    async def invalid(**kwargs: Any) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(type="text", content="invalid JSON")

    monkeypatch.setattr(provider_manager, "chat_stream", invalid)
    bid = await generation.generate_batch(date(2026, 10, 26), "admin")
    monkeypatch.setattr(provider_manager, "chat_stream", real_stream)
    selected, release = asyncio.Event(), asyncio.Event()
    factory = pool["factory"]

    def retry_session() -> Any:
        db = factory()
        scalar = db.scalar

        async def pause_before_run_lock(statement: Any, *args: Any, **kwargs: Any) -> Any:
            if (
                any(d.get("entity") is Run for d in statement.column_descriptions)
                and not selected.is_set()
            ):
                selected.set()
                await release.wait()
            return await scalar(statement, *args, **kwargs)

        db.scalar = pause_before_run_lock
        return db

    monkeypatch.setattr(generation, "get_session_factory", lambda: retry_session)
    pending = asyncio.create_task(generation.generate_batch(date(2026, 10, 26), "admin"))
    await asyncio.wait_for(selected.wait(), 10)
    async with factory() as db:
        await publishing.withdraw(db, bid, pool["users"][0], "withdraw failed generation")
        await db.commit()
    release.set()
    assert await pending == bid
    async with factory() as db:
        assert (await db.get(Batch, bid)).status == "withdrawn"
        assert (await db.scalar(select(Run).where(Run.batch_id == bid))).status == "cancelled"
    assert not pool["calls"], "A withdrawn retry invoked the model"


async def test_message_restore_refreshes_state_after_waiting_for_lock(
    pool: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cygnusx.application.schemas.welcome import MessageReviewRequest

    bid = await generate_and_publish(pool)
    selected, release = asyncio.Event(), asyncio.Event()
    real_lock = admin_api.lock_resource
    async with pool["factory"]() as restore_db:
        mid = await restore_db.scalar(select(Message.id).where(Message.batch_id == bid).limit(1))

        async def pause_before_review_lock(db: Any, key: str) -> None:
            if db is restore_db:
                selected.set()
                await release.wait()
            await real_lock(db, key)

        monkeypatch.setattr(admin_api, "lock_resource", pause_before_review_lock)
        pending = asyncio.create_task(
            admin_api.review_message(
                mid,
                MessageReviewRequest(enabled=True, note="restore after concurrent disable"),
                None,
                str(pool["users"][0]),
                restore_db,
            )
        )
        await asyncio.wait_for(selected.wait(), 10)
        async with pool["factory"]() as db:
            await admin_api.review_message(
                mid,
                MessageReviewRequest(enabled=False, note="disable"),
                None,
                str(pool["users"][1]),
                db,
            )
            await db.commit()
        release.set()
        await pending
        await restore_db.commit()
    async with pool["factory"]() as db:
        message = await db.get(Message, mid)
        assert message.enabled is True
        assert message.disabled_reason == "restore after concurrent disable"
