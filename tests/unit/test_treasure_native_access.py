"""P0: real JWT/ASGI routes + isolated SQLite, never a deployed service or queue."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from cygnusx.api import deps
from cygnusx.api.v1.research_agent import router
from cygnusx.application.services import research_treasure_service as research
from cygnusx.core import security
from cygnusx.core.exceptions import CygnusXError
from cygnusx.infrastructure.database.models.ai_provider import AIProviderConfigModel
from cygnusx.infrastructure.database.models.chat import (
    ChatMessageEventModel,
    ChatMessageModel,
    ChatSessionModel,
)
from cygnusx.infrastructure.database.models.project import ProjectModel
from cygnusx.infrastructure.database.models.user import UserModel

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]
TEST_KEY = "treasure-native-test-key-only-not-production"


@pytest.mark.parametrize("session_id,selected", [("global", False), ("owned", True)])
@pytest.mark.parametrize("gateway_enabled", [False, True])
async def test_stream_passes_current_platform_tools_and_project_state(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
    session_id: str, selected: bool, gateway_enabled: bool,
) -> None:
    from cygnusx.application.services import agent_tool_delegation, agent_tool_gateway

    settings = research.get_settings()
    settings.tool_gateway_read_enabled = gateway_enabled
    monkeypatch.setattr(agent_tool_gateway, "get_settings", lambda: settings)
    captured: list[dict[str, Any]] = []

    async def delegation(context: Any) -> str:
        assert context.session_id == session_id
        assert context.user_id == str(env.owner)
        return "isolated-delegation"

    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        captured.append(kwargs["platform_tools"])
        yield {"event": "end", "cards": [], "tools": []}

    monkeypatch.setattr(agent_tool_delegation, "issue_delegation", delegation)
    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    service = research.ResearchTreasureService(env.db)
    _ = [event async for event in service.stream_message(
        str(env.owner), session_id, "can you download?", None, "zh", uuid4(),
    )]
    assert len(captured) == 1
    envelope = captured[0]
    assert envelope["project_selected"] is selected
    if gateway_enabled:
        assert envelope["delegation"] == "isolated-delegation"
        ids = {item["capability_id"] for item in envelope["catalog"]}
        assert "downloads.describe_capabilities" in ids
        assert "downloads.prepare" in ids
        assert "analysis.prepare" in ids
        assert "downloads.submit" not in ids
        assert "analysis.submit" not in ids
    else:
        assert envelope == {"catalog": [], "project_selected": selected}


async def test_request_usage_snapshots_survive_replay_without_double_counting(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        nonlocal calls
        calls += 1
        yield {"event": "usage", "llm_calls": 1, "usage": {
            "prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12,
        }}
        yield {"event": "usage", "llm_calls": 2, "usage": {
            "prompt_tokens": 30, "completion_tokens": 5, "total_tokens": 35,
        }}
        yield {"event": "end", "cards": [], "tools": []}

    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    service = research.ResearchTreasureService(env.db)
    request_id = uuid4()
    first = [event async for event in service.stream_message(
        str(env.owner), "global", "usage fixture", None, "zh", request_id,
    )]
    replay = [event async for event in service.stream_message(
        str(env.owner), "global", "usage fixture", None, "zh", request_id,
    )]
    assert replay == first
    rows = await service.messages(str(env.owner), "global")
    assistant = next(row for row in rows if row.role == "assistant"
                     and row.metadata_json.get("research_request_id") == str(request_id))
    assert assistant.metadata_json["usage"]["total_tokens"] == 35
    assert assistant.metadata_json["llm_calls"] == 2
    assert calls == 1


@compiles(JSONB, "sqlite")
def sqlite_json(element: Any, compiler: Any, **kw: Any) -> str:
    return "JSON"


class OfflineDB(AsyncSession):
    """Actual SQLite SQL with an async facade; no sockets or external credentials."""

    def __init__(self, engine: Any) -> None:
        self.sync = Session(engine, expire_on_commit=False)

    async def get(self, model: Any, key: Any, **kw: Any) -> Any:
        return self.sync.get(model, key, **kw)

    async def execute(self, statement: Any, **kw: Any) -> Any:
        return self.sync.execute(statement, **kw)

    def add(self, instance: Any, **kw: Any) -> None:
        self.sync.add(instance)

    async def flush(self, **kw: Any) -> None:
        self.sync.flush()

    async def commit(self) -> None:
        self.sync.commit()

    async def rollback(self) -> None:
        self.sync.rollback()

    async def refresh(self, instance: Any, **kw: Any) -> None:
        self.sync.refresh(instance, **kw)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    for model in (UserModel, ProjectModel, AIProviderConfigModel, ChatSessionModel,
                  ChatMessageModel, ChatMessageEventModel):
        model.__table__.create(engine)
    db = OfflineDB(engine)
    owner, other, project, foreign, provider = [uuid4() for _ in range(5)]
    for uid in (owner, other):
        db.add(UserModel(id=uid, username=str(uid), email=f"{uid}@invalid.test",
                         hashed_password="unused", status="active", role="user", token_version=0))
    for pid, uid in ((project, owner), (foreign, other)):
        db.add(ProjectModel(id=pid, user_id=uid, slug=str(pid), name=str(pid)))
    for sid, uid, pid in (("global", owner, None), ("owned", owner, project),
                          ("foreign", other, foreign)):
        db.add(ChatSessionModel(session_id=sid, user_id=str(uid),
                                project_id=str(pid) if pid else None, model_id=provider,
                                title=sid, status="active",
                                sandbox_meta={"research_agent": research.RESEARCH_AGENT_MARKER}))
        db.add(ChatMessageModel(message_id=sid, session_id=sid, content=f"message-{sid}",
                                role="assistant", status="complete", metadata_json={}))
    db.sync.commit()
    settings = SimpleNamespace(treasure_native_ui_enabled=True,
        treasure_agent_url="http://isolated-node.invalid", treasure_agent_internal_token="test-only",
        tool_gateway_read_enabled=False, dataset_discovery_readonly=False,
        jwt_secret_key=TEST_KEY, jwt_algorithm="HS256")
    monkeypatch.setattr(research, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)

    @asynccontextmanager
    async def auth_db() -> AsyncIterator[OfflineDB]:
        yield db

    @asynccontextmanager
    async def worker_db() -> AsyncIterator[OfflineDB]:
        worker_session = OfflineDB(engine)
        try:
            yield worker_session
        finally:
            worker_session.sync.close()

    monkeypatch.setattr(deps, "get_session_factory", lambda: auth_db)
    monkeypatch.setattr(research, "get_session_factory", lambda: worker_db)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/research-agent")

    async def route_db() -> OfflineDB:
        return db

    app.dependency_overrides[deps.get_db] = route_db

    @app.exception_handler(CygnusXError)
    async def error_handler(request: Request, exc: CygnusXError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code,
                            content={"detail": exc.detail, "code": exc.code})

    def token(uid: UUID = owner, **claims: Any) -> dict[str, str]:
        payload = {"sub": str(uid), "type": "access", "token_version": 0,
                   "exp": datetime.now(UTC) + timedelta(minutes=5), **claims}
        return {"Authorization": "Bearer " + jwt.encode(payload, TEST_KEY, algorithm="HS256")}

    yield SimpleNamespace(app=app, db=db, owner=owner, other=other, project=project,
                          foreign=foreign, settings=settings, headers=token)
    db.sync.close()
    engine.dispose()


async def request(env: SimpleNamespace, method: str, path: str, **kwargs: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=env.app), base_url="http://isolated") as c:
        return await c.request(method, "/api/v1/research-agent" + path,
                               headers=kwargs.pop("headers", env.headers()), **kwargs)


async def test_capability_remains_readable_when_native_disabled(env: SimpleNamespace) -> None:
    env.settings.treasure_native_ui_enabled = False
    response = await request(env, "GET", "/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert {
        "native_ui_enabled", "enabled", "read_sessions", "read_discovery",
        "prepare_import", "prepare_analysis", "project_required_for_prepare",
        "write_execution", "write_tools_enabled", "reason_code", "cancellation_mode",
        "read_only", "supported_events",
    } <= body.keys()
    assert body["reason_code"] == "FEATURE_DISABLED"
    assert not any(body[name] for name in ("enabled", "read_sessions", "read_discovery",
                                         "prepare_import", "prepare_analysis", "write_execution"))
    assert body["write_execution"] is False
    assert body["write_tools_enabled"] is False


async def test_cancel_route_exposes_signal_state_not_completion(env: SimpleNamespace, monkeypatch) -> None:
    async def accepted(self: Any, user_id: str, session_id: str) -> str:
        assert session_id == "global"
        return "accepted"

    monkeypatch.setattr(research.ResearchTreasureService, "cancel", accepted)
    response = await request(env, "POST", "/sessions/global/cancel")
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/sessions", None), ("POST", "/sessions", {}),
    ("GET", "/sessions/owned/messages", None),
    ("POST", "/sessions/owned/messages:stream", {"content": "read only"}),
    ("POST", "/sessions/owned/cancel", None),
])
@pytest.mark.parametrize("enabled", [False, True])
async def test_module_revocation_denies_every_route_before_native_gate(
    env: SimpleNamespace, method: str, path: str, body: Any, enabled: bool,
) -> None:
    env.settings.treasure_native_ui_enabled = enabled
    user = env.db.sync.get(UserModel, env.owner)
    user.disabled_modules = ["treasure-mouse"]
    env.db.sync.commit()
    response = await request(env, method, path, json=body)
    assert response.status_code == 403
    assert response.json()["code"] == "MODULE_LOCKED"
    assert len(env.db.sync.scalars(select(ChatSessionModel)).all()) == 3
    assert len(env.db.sync.scalars(select(ChatMessageModel)).all()) == 3


async def test_permission_refresh_is_fail_closed(env: SimpleNamespace) -> None:
    assert (await request(env, "GET", "/capabilities")).json()["read_sessions"]
    env.db.sync.get(UserModel, env.owner).disabled_modules = ["treasure-mouse"]
    env.db.sync.commit()
    body = (await request(env, "GET", "/capabilities")).json()
    assert body["reason_code"] == "MODULE_LOCKED" and not body["read_sessions"]


@pytest.mark.parametrize("headers", ["anonymous", "expired", "wrong_version", "invalid"])
async def test_real_jwt_authentication_rejects_invalid_identity(
    env: SimpleNamespace, headers: str,
) -> None:
    options = {
        "anonymous": {},
        "expired": env.headers(exp=datetime.now(UTC) - timedelta(minutes=1)),
        "wrong_version": env.headers(token_version=99),
        "invalid": {"Authorization": "Bearer not-a-jwt"},
    }
    response = await request(env, "GET", "/capabilities", headers=options[headers])
    assert response.status_code == 401


async def test_global_history_and_message_dto_without_project_or_old_chat_runtime(
    env: SimpleNamespace,
) -> None:
    response = await request(env, "GET", "/sessions")
    assert response.status_code == 200
    assert [s["session_id"] for s in response.json()] == ["global"]
    messages = await request(env, "GET", "/sessions/global/messages")
    assert messages.status_code == 200
    assert messages.json()[0]["content"] == "message-global"


@pytest.mark.parametrize("path,status", [
    ("/sessions/foreign/messages", 404),
    ("/sessions/foreign/messages:stream", 404),
    ("/sessions?project_id=foreign", 403),
    ("/sessions?project_id=bad-uuid", 422),
])
async def test_owner_scope_errors_remain_http_errors(
    env: SimpleNamespace, path: str, status: int,
) -> None:
    path = path.replace("project_id=foreign", "project_id=" + str(env.foreign))
    method = "POST" if path.endswith(":stream") else "GET"
    response = await request(env, method, path, json={"content": "query"} if method == "POST" else None)
    assert response.status_code == status
    assert "text/event-stream" not in response.headers.get("content-type", "")


async def test_disabled_native_and_unavailable_provider_are_distinct(env: SimpleNamespace) -> None:
    env.settings.treasure_native_ui_enabled = False
    response = await request(env, "GET", "/sessions")
    assert response.status_code == 403 and response.json()["code"] == "FEATURE_DISABLED"
    env.settings.treasure_native_ui_enabled = True
    response = await request(env, "POST", "/sessions", json={})
    assert response.status_code == 503 and response.json()["code"] == "PROVIDER_UNAVAILABLE"


async def test_admin_can_access_module_but_not_another_owners_project(env: SimpleNamespace) -> None:
    user = env.db.sync.get(UserModel, env.owner)
    user.role = "admin"
    user.disabled_modules = ["treasure-mouse"]
    env.db.sync.commit()
    assert (await request(env, "GET", "/capabilities")).json()["enabled"]
    response = await request(env, "GET", "/sessions?project_id=" + str(env.foreign))
    assert response.status_code == 403


async def test_prepare_capabilities_respect_modules_and_never_advertise_execution(
    env: SimpleNamespace,
) -> None:
    env.settings.tool_gateway_read_enabled = True
    env.settings.dataset_discovery_readonly = True
    body = (await request(env, "GET", "/capabilities")).json()
    assert body["prepare_import"] and body["prepare_analysis"]
    assert body["project_required_for_prepare"] and not body["write_execution"]
    env.db.sync.get(UserModel, env.owner).disabled_modules = ["flows", "downloads"]
    env.db.sync.commit()
    body = (await request(env, "GET", "/capabilities")).json()
    assert body["read_discovery"] and not body["prepare_import"] and not body["prepare_analysis"]


async def test_downstream_configuration_not_confused_with_empty_history(env: SimpleNamespace) -> None:
    env.settings.treasure_agent_internal_token = ""
    body = (await request(env, "GET", "/capabilities")).json()
    assert body["read_sessions"] and not body["read_discovery"]
    assert body["reason_code"] == "NODE_NOT_CONFIGURED"


async def test_manual_session_rename_locks_generated_title(env: SimpleNamespace) -> None:
    response = await request(env, "PATCH", "/sessions/global", json={"title": "手动标题"})
    assert response.status_code == 200
    assert response.json()["title"] == "手动标题"
    assert response.json()["title_locked"] is True

async def test_stream_provider_failure_is_http_503_before_sse(env: SimpleNamespace) -> None:
    response = await request(env, "POST", "/sessions/global/messages:stream", json={"content": "read"})
    assert response.status_code == 503
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"
    assert "text/event-stream" not in response.headers.get("content-type", "")


@pytest.mark.parametrize("failure_mode", ["exception", "event"])
async def test_stream_persists_messages_and_sanitizes_downstream_failure(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, failure_mode: str
) -> None:
    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **kw: Any) -> AsyncIterator[dict[str, Any]]:
        yield {"event": "delta", "delta": "已发现"}
        if failure_mode == "event":
            yield {"event": "error", "error": "SECRET INTERNAL TRACE"}
        else:
            raise RuntimeError("SECRET INTERNAL TRACE")

    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    response = await request(env, "POST", "/sessions/global/messages:stream", json={"content": "read"})
    assert response.status_code == 200
    assert "NODE_UNAVAILABLE" in response.text
    assert "SECRET" not in response.text
    restored = await request(env, "GET", "/sessions/global/messages")
    rows = restored.json()
    assert any(row["role"] == "user" and row["content"] == "read" for row in rows)
    assert any(row["content"] == "已发现" and row["status"] == "error" for row in rows)


async def test_cancelled_stream_commits_partial_snapshot_before_request_rollback(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        yield {"event": "delta", "delta": "已收到部分结果"}
        await asyncio.Event().wait()

    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    service = research.ResearchTreasureService(env.db)
    response = service.stream_message(str(env.owner), "global", "read", None, "zh", uuid4())
    assert await anext(response) == {
        "event": "delta", "delta": "已收到部分结果", "_sse_id": 1,
    }

    async def next_event() -> dict[str, Any]:
        return await anext(response)

    pending: asyncio.Task[dict[str, Any]] = asyncio.create_task(next_event())
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending

    # The request-scoped dependency rolls back its session after cancellation.
    await env.db.rollback()
    rows = await service.messages(str(env.owner), "global")
    assert any(row.role == "user" and row.content == "read" for row in rows)
    assistant = next(row for row in rows if row.role == "assistant" and row.content == "已收到部分结果")
    assert assistant.status == "cancel"


async def test_stream_retry_replays_same_generation_after_cursor_without_second_agent_call(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        nonlocal calls
        calls += 1
        yield {"event": "delta", "delta": "one"}
        card = {"accession": "GSE12345", "title": "study", "meta": {"samples": 4}}
        yield {"event": "cards", "cards": [card]}
        yield {"event": "tool", "name": "search_geo", "status": "done"}
        yield {"event": "end", "cards": [card],
               "tools": [{"name": "search_geo", "status": "done"}]}

    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    request_id = str(uuid4())
    body = {"content": "read", "request_id": request_id}
    first = await request(env, "POST", "/sessions/global/messages:stream", json=body)
    assert first.status_code == 200
    frames = [frame for frame in first.text.split("\n\n") if frame.startswith("id:")]
    assert len(frames) == 4
    assert frames[0].startswith("id: 1\ndata: ")

    resumed = await request(
        env, "POST", "/sessions/global/messages:stream", json=body,
        headers={**env.headers(), "Last-Event-ID": "1"},
    )
    assert resumed.status_code == 200
    assert "id: 1\n" not in resumed.text
    assert all(f"id: {seq}\n" in resumed.text for seq in (2, 3, 4))
    assert calls == 1
    conflict = await request(
        env, "POST", "/sessions/global/messages:stream",
        json={"content": "different payload", "request_id": request_id},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert calls == 1
    assistant = next(
        row for row in (await request(env, "GET", "/sessions/global/messages")).json()
        if row["role"] == "assistant" and row["metadata_json"].get("research_request_id") == request_id
    )
    assert assistant["content"] == "one"
    assert assistant["status"] == "end"
    assert assistant["metadata_json"]["events"]["cards"] == [
        {"accession": "GSE12345", "title": "study", "meta": {"samples": 4}},
    ]
    assert assistant["metadata_json"]["events"]["tools"] == [
        {"name": "search_geo", "status": "done"},
    ]


async def test_generation_continues_after_replay_consumer_disconnects(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    continue_generation = asyncio.Event()

    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        nonlocal calls
        calls += 1
        yield {"event": "delta", "delta": "first"}
        await continue_generation.wait()
        yield {"event": "delta", "delta": "second"}
        yield {"event": "end"}

    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    request_id = uuid4()
    service = research.ResearchTreasureService(env.db)
    await service.ensure_generation_running(
        str(env.owner), "global", "read", None, "zh", request_id
    )

    disconnected = service.stream_message(
        str(env.owner), "global", "read", None, "zh", request_id
    )
    first = await anext(disconnected)
    assert first["delta"] == "first"
    await disconnected.aclose()

    continue_generation.set()
    key = ("global", request_id)
    task = research.ResearchTreasureService._generation_tasks[key]
    await asyncio.wait_for(task, timeout=2)

    resumed = service.stream_message(
        str(env.owner), "global", "read", None, "zh", request_id, cursor=first["_sse_id"]
    )
    events = [event async for event in resumed]
    assert [event["event"] for event in events] == ["delta", "end"]
    assert [event.get("delta") for event in events] == ["second", None]
    assert calls == 1


async def test_cancel_endpoint_reaches_active_stream_from_another_service_instance(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        yield {"event": "delta", "delta": "partial"}
        await kwargs["cancel_event"].wait()
        yield {"event": "cancel"}

    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    running_service = research.ResearchTreasureService(env.db)
    events = running_service.stream_message(
        str(env.owner), "global", "read", None, "zh", uuid4()
    )
    assert (await anext(events))["delta"] == "partial"
    cancel_service = research.ResearchTreasureService(env.db)
    assert await cancel_service.cancel(str(env.owner), "global") == "accepted"
    terminal = await anext(events)
    assert terminal["event"] == "cancel"
    with pytest.raises(StopAsyncIteration):
        await anext(events)


async def test_cancel_without_local_producer_reports_unknown(env: SimpleNamespace) -> None:
    service = research.ResearchTreasureService(env.db)
    assert await service.cancel(str(env.owner), "global") == "unknown"


async def test_cancel_persists_signal_for_remote_producer(env: SimpleNamespace) -> None:
    assistant = env.db.sync.scalar(
        select(ChatMessageModel).where(ChatMessageModel.message_id == "global")
    )
    assert assistant is not None
    assistant.status = "streaming"
    env.db.sync.commit()

    service = research.ResearchTreasureService(env.db)
    assert await service.cancel(str(env.owner), "global") == "accepted"

    env.db.sync.refresh(assistant)
    assert assistant.metadata_json["cancel_requested"] is True
    assert "cancel_requested_at" in assistant.metadata_json


async def test_remote_cancel_signal_terminates_stream_on_next_event(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **_: Any) -> AsyncIterator[dict[str, Any]]:
        yield {"event": "delta", "delta": "partial"}
        await asyncio.sleep(0.2)
        yield {"event": "delta", "delta": "late"}

    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    research.ResearchTreasureService._active_cancels.clear()
    request_id = uuid4()
    running = research.ResearchTreasureService(env.db)
    events = running.stream_message(str(env.owner), "global", "read", None, "zh", request_id)
    assert (await anext(events))["delta"] == "partial"
    research.ResearchTreasureService._active_cancels.clear()

    remote = research.ResearchTreasureService(env.db)
    assert await remote.cancel(str(env.owner), "global") == "accepted"
    assert (await anext(events))["event"] == "cancel"
    with pytest.raises(StopAsyncIteration):
        await anext(events)

async def test_inactive_user_cannot_read_capabilities(env: SimpleNamespace) -> None:
    user = env.db.sync.get(UserModel, env.owner)
    user.status = "disabled"
    env.db.sync.commit()
    response = await request(env, "GET", "/capabilities")
    assert response.status_code == 401


async def test_presentation_session_edit_is_owner_scoped_and_archive_is_soft(
    env: SimpleNamespace,
) -> None:
    denied = await request(env, "PATCH", "/sessions/foreign", json={"title": "not mine"})
    assert denied.status_code == 404
    renamed = await request(env, "PATCH", "/sessions/global", json={"title": "新的研究主题"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "新的研究主题"
    archived = await request(env, "PATCH", "/sessions/global", json={"status": "archived"})
    assert archived.status_code == 200
    rows = (await request(env, "GET", "/sessions")).json()
    assert all(row["session_id"] != "global" for row in rows)
    assert (await request(env, "GET", "/sessions/global/messages")).status_code == 404
    saved = env.db.sync.execute(select(ChatSessionModel).where(
        ChatSessionModel.session_id == "global",
    )).scalar_one()
    assert saved.status == "archived"


async def test_literature_is_authenticated_session_owned_and_input_validated(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def literature(self: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"status": "ok", "title": "Isolated evidence", "pmid": "12345678"}

    monkeypatch.setattr(research.TreasureAgentAdapter, "literature", literature)
    assert (await request(env, "POST", "/sessions/foreign/literature", json={
        "kind": "pubmed", "id": "12345678",
    })).status_code == 404
    assert not calls
    assert (await request(env, "POST", "/sessions/global/literature", json={
        "kind": "pubmed", "id": "https://internal.invalid/",
    })).status_code == 422
    result = await request(env, "POST", "/sessions/global/literature", json={
        "kind": "pubmed", "id": "12345678",
    })
    assert result.status_code == 200
    assert calls == [{"kind": "pubmed", "identifier": "12345678", "principal_id": str(env.owner)}]
    env.db.sync.get(UserModel, env.owner).disabled_modules = ["treasure-mouse"]
    assert (await request(env, "POST", "/sessions/global/literature", json={
        "kind": "pubmed", "id": "12345678",
    })).status_code == 403
    assert len(calls) == 1


async def test_node_adapter_does_not_inherit_host_proxy_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_client = research.httpx.AsyncClient
    client_options: list[dict[str, Any]] = []

    async def handler(request: Any) -> Any:
        if request.url.path.endswith("/discovery"):
            if request.headers.get("accept") == "text/event-stream":
                return research.httpx.Response(
                    200, text='data: {"event":"end"}\n\ndata: [DONE]\n\n'
                )
            return research.httpx.Response(200, json={"status": "ok", "title": "paper"})
        raise AssertionError(f"unexpected Node URL: {request.url}")

    transport = research.httpx.MockTransport(handler)

    def client_factory(**kwargs: Any) -> Any:
        client_options.append(dict(kwargs))
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr(research.httpx, "AsyncClient", client_factory)
    settings = SimpleNamespace(
        treasure_agent_url="http://node.internal",
        treasure_agent_internal_token="isolated-test-token",
        treasure_agent_timeout_seconds=5,
    )
    adapter = research.TreasureAgentAdapter(settings)

    detail = await adapter.literature(
        kind="pubmed", identifier="12345", principal_id="user-1"
    )
    assert detail["status"] == "ok"
    events = [
        event async for event in adapter.stream(
            messages=[{"role": "user", "content": "find papers"}],
            model="test-model",
            lang="en",
            cancel_event=asyncio.Event(),
            principal_id="user-1",
            project_id=None,
            session_id="session-1",
        )
    ]
    assert events == [{"event": "end"}]
    assert len(client_options) == 2
    assert all(options["trust_env"] is False for options in client_options)


@pytest.mark.parametrize("terminal", ["end", "eof"])
async def test_original_result_payload_survives_stream_and_history(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, terminal: str,
) -> None:
    first = {"tool": "search_geo", "accession": "GSE12345", "title": "study",
             "meta": {"organism": "Mus musculus", "samples": "12"}}
    paper = {"tool": "literature_search", "accession": "PMID12345678", "title": "paper",
             "summary": "abstract", "meta": {"source": "literature", "doi": "10.1000/test",
                                               "authors": "A; B", "year": "2025"}}

    async def provider(self: Any, model_id: Any) -> Any:
        return SimpleNamespace(model="isolated-test-model")

    async def stream(self: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        yield {"delta": "研究结果"}
        yield {"event": "cards", "cards": [first]}
        yield {"event": "polariseq", "accession": "PRJNA12345"}
        yield {"event": "grounding", "unconfirmed": [{"id": "GSE99999", "status": "unverified"}]}
        if terminal == "end":
            yield {"event": "end", "cards": [first, paper],
                   "tools": [{"name": "search_geo", "label": "GEO", "ok": True, "ms": 25}]}

    monkeypatch.setattr(research.ResearchTreasureService, "_provider", provider)
    monkeypatch.setattr(research.TreasureAgentAdapter, "stream", stream)
    assert (await request(env, "POST", "/sessions/global/messages:stream", json={"content": "read"})).status_code == 200
    rows = (await request(env, "GET", "/sessions/global/messages")).json()
    message = next(row for row in rows if row["content"] == "研究结果")
    assert message["status"] == ("end" if terminal == "end" else "interrupted")
    events = message["metadata_json"]["events"]
    assert events["cards"] == ([first, paper] if terminal == "end" else [first])
    assert events["polariseq"] == {"accession": "PRJNA12345"}
    assert events["grounding"]["unconfirmed"][0]["id"] == "GSE99999"
