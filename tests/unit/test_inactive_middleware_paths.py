"""Inactive middleware must relay ASGI directly; active guards remain mandatory."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from cygnusx.middleware.audit import AuditMiddleware
from cygnusx.middleware.cookie import CookieRequiredMiddleware

pytestmark = pytest.mark.unit


async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
    await JSONResponse({"accepted": True}, status_code=201)(scope, receive, send)


@pytest.mark.parametrize("middleware", [AuditMiddleware, CookieRequiredMiddleware])
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/tasks"),
        ("HEAD", "/api/v1/tasks"),
        ("OPTIONS", "/api/v1/tasks"),
    ],
)
async def test_read_requests_do_not_enter_body_relay(
    middleware: type[AuditMiddleware] | type[CookieRequiredMiddleware],
    method: str,
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "cygnusx.middleware.cookie.get_settings", lambda: SimpleNamespace(enable_cookie_system=True)
    )
    instance = middleware(downstream)
    instance.dispatch_func = AsyncMock(side_effect=AssertionError("Inactive dispatch entered"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=instance), base_url="http://test"
    ) as c:
        response = await c.request(method, path)
    assert response.status_code == 201
    instance.dispatch_func.assert_not_awaited()


@pytest.mark.parametrize("middleware", [AuditMiddleware, CookieRequiredMiddleware])
async def test_websocket_is_passed_through_untouched(
    middleware: type[AuditMiddleware] | type[CookieRequiredMiddleware],
) -> None:
    scope: Scope = {"type": "websocket", "path": "/ws"}
    receive = AsyncMock()
    send = AsyncMock()
    app = AsyncMock()
    await middleware(app)(scope, receive, send)
    app.assert_awaited_once_with(scope, receive, send)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_writes_are_still_audited(method: str, monkeypatch: pytest.MonkeyPatch) -> None:
    record = AsyncMock()
    monkeypatch.setattr(AuditMiddleware, "_record", record)
    app = AuditMiddleware(downstream)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.request(method, "/api/v1/projects/run")
    assert response.status_code == 201
    record.assert_awaited_once()
    request, result = record.await_args.args
    assert isinstance(request, Request) and request.method == method
    assert result.status_code == 201


async def test_frozen_account_still_blocks_consumption(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cygnusx.middleware.cookie.get_settings", lambda: SimpleNamespace(enable_cookie_system=True)
    )
    check = AsyncMock(return_value=Response(status_code=402))
    monkeypatch.setattr(CookieRequiredMiddleware, "_check_account", check)
    handler = AsyncMock(side_effect=AssertionError("Blocked request reached business handler"))
    middleware = CookieRequiredMiddleware(handler)

    async def identified(scope: Scope, receive: Receive, send: Send) -> None:
        scope.setdefault("state", {})["user_id"] = "test-user"
        await middleware(scope, receive, send)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=identified), base_url="http://test"
    ) as c:
        response = await c.post("/api/v1/tasks")
    assert response.status_code == 402
    check.assert_awaited_once_with("test-user")
    handler.assert_not_awaited()


@pytest.mark.parametrize("enabled,path", [(False, "/api/v1/tasks"), (True, "/api/v1/auth/login")])
async def test_non_consuming_paths_do_not_enter_guard(
    enabled: bool,
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "cygnusx.middleware.cookie.get_settings",
        lambda: SimpleNamespace(enable_cookie_system=enabled),
    )
    middleware = CookieRequiredMiddleware(downstream)
    middleware.dispatch_func = AsyncMock(side_effect=AssertionError("Inactive guard entered"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=middleware), base_url="http://test"
    ) as c:
        response = await c.post(path)
    assert response.status_code == 201
    middleware.dispatch_func.assert_not_awaited()


@pytest.mark.parametrize("middleware", [AuditMiddleware, CookieRequiredMiddleware])
async def test_stream_first_chunk_does_not_wait_for_completion(
    middleware: type[AuditMiddleware] | type[CookieRequiredMiddleware],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "cygnusx.middleware.cookie.get_settings", lambda: SimpleNamespace(enable_cookie_system=True)
    )
    monkeypatch.setattr(AuditMiddleware, "_record", AsyncMock())
    first = asyncio.Event()
    finish = asyncio.Event()
    disconnected = asyncio.Event()
    chunks: list[bytes] = []

    async def stream(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"data: first\n\n", "more_body": True})
        await finish.wait()
        await send({"type": "http.response.body", "body": b"data: done\n\n", "more_body": False})

    async def receive() -> dict[str, object]:
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        if message["type"] == "http.response.body":
            body = message.get("body", b"")
            assert isinstance(body, bytes)
            chunks.append(body)
            if body:
                first.set()

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/chat/stream",
        "headers": [],
        "asgi": {"spec_version": "2.4"},
    }
    task = asyncio.create_task(middleware(stream)(scope, receive, send))
    try:
        await asyncio.wait_for(first.wait(), timeout=1)
        assert not task.done()
    finally:
        finish.set()
        await asyncio.wait_for(task, timeout=1)
    assert b"".join(chunks) == b"data: first\n\ndata: done\n\n"
