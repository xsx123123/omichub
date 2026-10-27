"""Check that the load generator cannot report denied/broken API responses as capacity."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncIterator

import pytest
from aiohttp import web
from scripts.web_load_test import run_stage

pytestmark = pytest.mark.unit


@pytest.fixture
async def probe_server(unused_tcp_port: int) -> AsyncIterator[tuple[str, dict[str, int]]]:
    concurrency = {"active": 0, "max": 0}

    async def respond(request: web.Request) -> web.Response:
        concurrency["active"] += 1
        concurrency["max"] = max(concurrency["max"], concurrency["active"])
        try:
            await asyncio.sleep(0.01)
            if request.path == "/ok":
                return web.json_response({"status": "ok"})
            if request.path == "/denied":
                return web.json_response({"detail": "denied"}, status=401)
            if request.path == "/busy":
                return web.Response(status=503, text="limited")
            return web.Response(text="<html>SPA fallback</html>", content_type="text/html")
        finally:
            concurrency["active"] -= 1

    app = web.Application()
    app.router.add_get("/{path}", respond)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
    try:
        yield f"http://127.0.0.1:{unused_tcp_port}", concurrency
    finally:
        await runner.cleanup()


def options(base_url: str, path: str) -> argparse.Namespace:
    return argparse.Namespace(
        base_url=base_url, paths=[path], profile="public", timeout=1, think_time=0
    )


async def test_successful_concurrency(probe_server: tuple[str, dict[str, int]]) -> None:
    url, concurrency = probe_server
    result = await run_stage(options(url, "/ok"), [], 4, 0.15)
    assert concurrency["max"] == 4
    assert result["requests"] == result["successful_requests"] > 4
    assert result["error_rate"] == 0
    assert result["successful_latency_ms"]["p95"] > 0


@pytest.mark.parametrize(
    "path,error",
    [
        ("/denied", "401"),
        ("/busy", "503"),
        ("/fallback", "invalid_body"),
    ],
)
async def test_errors_are_not_successful_rps(
    probe_server: tuple[str, dict[str, int]], path: str, error: str
) -> None:
    result = await run_stage(options(probe_server[0], path), [], 2, 0.1)
    assert result["requests"] > 0
    assert result["successful_rps"] == 0
    assert result["error_rate"] == 1
    assert result["errors"][error] == result["requests"]
