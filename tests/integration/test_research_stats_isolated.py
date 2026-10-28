"""Real PostgreSQL, isolated schema and HTTP/JWT tests; no business rows are written."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cygnusx.api import deps
from cygnusx.api.v1 import research_agent
from cygnusx.application.services.research_stats_service import NICKNAME_KEY
from cygnusx.application.services.research_treasure_service import RESEARCH_AGENT_MARKER
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import CygnusXError
from cygnusx.core.security import create_access_token
from cygnusx.infrastructure.database.models.chat import ChatMessageModel, ChatSessionModel
from cygnusx.infrastructure.database.models.user import UserModel

pytestmark = pytest.mark.integration


@pytest.fixture
async def stats_api(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[dict[str, Any]]:
    settings = get_settings()
    url = make_url(settings.database_url)
    if url.host == "db":
        url = url.set(host="127.0.0.1")
    admin = create_async_engine(url)
    schema = "research_stats_test_" + uuid4().hex
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            for table in ("users", "chat_sessions", "chat_messages"):
                await connection.execute(text(
                    f'CREATE TABLE "{schema}".{table} (LIKE public.{table} INCLUDING DEFAULTS)'
                ))
    except Exception:
        await admin.dispose()
        raise
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(deps, "get_session_factory", lambda: factory)
    monkeypatch.setattr(settings, "treasure_native_ui_enabled", True)
    monkeypatch.setattr(settings, "treasure_stats_timezone", "Asia/Shanghai")
    owner, other, disabled = uuid4(), uuid4(), uuid4()
    app = FastAPI()
    app.include_router(research_agent.router, prefix="/api/v1/research-agent")

    @app.exception_handler(CygnusXError)
    async def error_handler(_request: Request, exc: CygnusXError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=exc.status_code)

    now = datetime.now(UTC)
    old = now - timedelta(days=14)
    async with factory() as db:
        for uid, name, status, nickname in (
            (owner, "private-login", "active", "平台公开昵称"),
            (other, "other-private-login", "active", "另一位研究者"),
            (disabled, "disabled", "disabled", "禁用账号"),
        ):
            db.add(UserModel(
                id=uid, username=name, email=f"{uid}@private.test", hashed_password="private-hash",
                role="user", status=status, nickname=nickname, preferences={"theme": "dark"},
                disabled_modules=[],
            ))
        for uid, suffix, marker in (
            (owner, "owner", RESEARCH_AGENT_MARKER),
            (other, "other", RESEARCH_AGENT_MARKER),
            (owner, "ordinary", "ordinary-chat"),
            (disabled, "disabled", RESEARCH_AGENT_MARKER),
        ):
            db.add(ChatSessionModel(
                id=uuid4(), session_id=suffix, user_id=str(uid), title="private research title",
                model_id=uuid4(), status="archived" if suffix == "owner" else "active",
                sandbox_meta={"research_agent": marker},
            ))
        await db.flush()

        def message(session: str, count: int, created: datetime, status: str = "end") -> None:
            cards = [{"accession": f"GSE{i}", "title": "private study"} for i in range(count)]
            db.add(ChatMessageModel(
                id=uuid4(), message_id=uuid4().hex, session_id=session, role="assistant",
                status=status, content="private content must never appear in public aggregates",
                created_at=created,
                metadata_json={"events": {"cards": cards + cards, "tools": [
                    {"name": "search_geo", "status": "running"},
                    {"name": "search_geo", "status": "done", "label": "检索"},
                    {"name": "search_sra", "ok": False},
                    {"name": "grounding_check", "ok": False},
                    {"name": "intent_plan", "ok": True},
                ]}, "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                    "llm_calls": 2},
            ))
        message("owner", 4, old)
        message("owner", 1, now)
        message("other", 3, now)
        message("ordinary", 99, now)
        message("disabled", 99, now)
        message("owner", 99, now, "streaming")
        await db.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.headers["Authorization"] = "Bearer " + create_access_token(str(owner), token_version=0)
        try:
            yield {"client": client, "factory": factory, "owner": owner, "other": other}
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()


async def test_rankings_are_real_deduplicated_weekly_and_private(stats_api: dict[str, Any]) -> None:
    client = stats_api["client"]
    all_time = (await client.get("/api/v1/research-agent/leaderboard")).json()
    week = (await client.get("/api/v1/research-agent/leaderboard?period=week")).json()
    assert all_time["users"][0]["name"] == "平台公开昵称"
    assert week["users"][0]["name"] == "另一位研究者"
    assert all_time["users"][0]["treasures"] == 5
    assert all_time["totalTreasures"] == 8
    assert all_time["weekTreasures"] == 4
    assert all_time["guests"] == []
    assert all_time["ownKey"] == all_time["users"][0]["key"]
    serialized = str(all_time)
    for private in ("private-login", "@private.test", "private content", "private study",
                    "private-hash", "private research title", str(stats_api["owner"])):
        assert private not in serialized
    assert (await client.get("/api/v1/research-agent/leaderboard")).json() == all_time


async def test_usage_counts_only_platform_terminal_records(stats_api: dict[str, Any]) -> None:
    response = await stats_api["client"].get("/api/v1/research-agent/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["chats"] == 3
    assert data["actors"] == 2
    assert data["toolCalls"] == 6
    assert data["toolErrors"] == 3
    assert data["totalTokens"] == 45
    assert data["llmCalls"] == 6
    assert data["usageRecordedChats"] == 3
    assert {item["name"] for item in data["tools"]} == {"search_geo", "search_sra"}


async def test_nickname_is_persisted_owner_scoped_and_validated(stats_api: dict[str, Any]) -> None:
    client = stats_api["client"]
    response = await client.patch("/api/v1/research-agent/nickname", json={"nickname": "  探矿员  "})
    assert response.status_code == 200
    assert response.json()["nickname"] == "探矿员"
    async with stats_api["factory"]() as db:
        user = await db.get(UserModel, stats_api["owner"])
        other = await db.get(UserModel, stats_api["other"])
        assert user.preferences == {"theme": "dark", NICKNAME_KEY: "探矿员"}
        assert user.username == "private-login" and user.nickname == "平台公开昵称"
        assert NICKNAME_KEY not in other.preferences
    assert (await client.get("/api/v1/research-agent/leaderboard")).json()["nickname"] == "探矿员"
    for nickname in (" ", "x" * 17, "a\nb"):
        assert (await client.patch("/api/v1/research-agent/nickname", json={"nickname": nickname})).status_code == 422
    assert (await client.patch("/api/v1/research-agent/nickname", json={
        "nickname": "不能修改他人", "user_id": str(stats_api["other"]),
    })).status_code == 422


async def test_all_stats_routes_require_auth_and_module_access(stats_api: dict[str, Any]) -> None:
    client = stats_api["client"]
    for path in ("leaderboard", "stats"):
        token = client.headers.pop("Authorization")
        assert (await client.get(f"/api/v1/research-agent/{path}")).status_code == 401
        client.headers["Authorization"] = token
    async with stats_api["factory"]() as db:
        user = await db.get(UserModel, stats_api["owner"])
        user.disabled_modules = ["treasure-mouse"]
        await db.commit()
    assert (await client.get("/api/v1/research-agent/leaderboard")).status_code == 403
    assert (await client.get("/api/v1/research-agent/stats")).status_code == 403
    assert (await client.patch("/api/v1/research-agent/nickname", json={"nickname": "无权改名"})).status_code == 403
