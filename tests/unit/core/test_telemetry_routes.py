"""Route-label caching must preserve live handlers, spans, metrics and invalidation."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import APIRouter, FastAPI, Header, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from starlette.routing import Route
from starlette.types import Scope

from cygnusx.core.telemetry_routes import StaticRouteSpanDetails, install_static_route_span_cache

pytestmark = pytest.mark.unit


@pytest.fixture
def providers() -> Iterator[tuple[TracerProvider, MeterProvider]]:
    tracer = TracerProvider()
    meter = MeterProvider()
    try:
        yield tracer, meter
    finally:
        tracer.shutdown()
        meter.shutdown()


def scope(app: Any, path: str = "/one", *, method: str = "GET", host: str = "test") -> Scope:
    return {
        "type": "http",
        "app": app,
        "path": path,
        "root_path": "",
        "method": method,
        "scheme": "http",
        "server": ("test", 80),
        "headers": [(b"host", host.encode())],
    }


def test_bounded_lru_and_attribute_isolation() -> None:
    app = object()
    calls: list[str] = []

    def resolver(request: Scope) -> tuple[str, dict[str, Any]]:
        calls.append(request["path"])
        return f"GET {request['path']}", {"http.route": request["path"]}

    cache = StaticRouteSpanDetails(
        app,
        resolver,
        lambda: 1,
        lambda: {"/one", "/two", "/three"},
        max_entries=2,
        max_key_chars=2048,
    )
    cache(scope(app))[1]["http.route"] = "mutated"
    assert cache(scope(app))[1] == {"http.route": "/one"}
    cache(scope(app, "/two"))
    cache(scope(app, "/one"))
    cache(scope(app, "/three"))
    cache(scope(app, "/two"))
    assert calls == ["/one", "/two", "/three", "/two"]
    assert cache.statistics() == {"hits": 2, "misses": 4, "entries": 2}


def test_unknown_dynamic_and_oversized_paths_are_never_retained() -> None:
    app = object()
    count = 0

    def resolver(request: Scope) -> tuple[str, dict[str, Any]]:
        nonlocal count
        count += 1
        return f"GET {request['path']}", {"http.route": request["path"]}

    cache = StaticRouteSpanDetails(
        app, resolver, lambda: 1, lambda: {"/one"}, max_entries=2, max_key_chars=20
    )
    for path in ("/unknown", "/users/123", "/" + "a" * 100):
        cache(scope(app, path))
        cache(scope(app, path))
    assert count == 6
    assert cache.statistics()["entries"] == 0


def test_method_host_and_root_path_are_not_confused() -> None:
    app = object()
    count = 0

    def resolver(request: Scope) -> tuple[str, dict[str, Any]]:
        nonlocal count
        count += 1
        return f"{request['method']} /one", {"http.route": "/one"}

    cache = StaticRouteSpanDetails(
        app, resolver, lambda: 1, lambda: {"/one"}, max_entries=8, max_key_chars=2048
    )
    variants = [scope(app), scope(app, method="POST"), scope(app, host="another")]
    root_scope = scope(app)
    root_scope["root_path"] = "/prefix"
    variants.append(root_scope)
    for request in variants:
        cache(request)
        cache(request)
    assert count == 4 and cache.statistics()["hits"] == 4


def test_version_changes_and_errors_do_not_serve_stale_labels() -> None:
    app = object()
    state: dict[str, Any] = {"version": 1, "error": False}

    def version() -> int:
        if state["error"]:
            raise RuntimeError("unavailable version")
        return int(state["version"])

    def resolver(request: Scope) -> tuple[str, dict[str, Any]]:
        return "GET /one", {"http.route": "/one", "revision": state["version"]}

    # Custom attributes must not enter the cache.
    cache = StaticRouteSpanDetails(
        app, resolver, version, lambda: {"/one"}, max_entries=8, max_key_chars=2048
    )
    assert cache(scope(app))[1]["revision"] == 1
    state["version"] = 2
    assert cache(scope(app))[1]["revision"] == 2
    state["error"] = True
    assert cache(scope(app))[1]["revision"] == 2
    assert cache.statistics()["entries"] == 0


async def test_live_auth_handlers_spans_and_histograms_are_not_cached() -> None:
    app = FastAPI()
    calls = 0

    @app.get("/secure")
    async def secure(authorization: str | None = Header(default=None)) -> dict[str, int]:
        nonlocal calls
        calls += 1
        if authorization != "Bearer example":
            raise HTTPException(status_code=401)
        return {"call": calls}

    exporter = InMemorySpanExporter()
    tracer = TracerProvider()
    tracer.add_span_processor(SimpleSpanProcessor(exporter))
    reader = InMemoryMetricReader()
    meter = MeterProvider(metric_readers=[reader])
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer, meter_provider=meter)
    assert install_static_route_span_cache(app, max_entries=8, max_key_chars=2048)
    assert not install_static_route_span_cache(app, max_entries=8, max_key_chars=2048)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            assert (await c.get("/secure", headers={"Authorization": "Bearer example"})).json() == {
                "call": 1
            }
            assert (await c.get("/secure")).status_code == 401
            assert (await c.get("/secure", headers={"Authorization": "Bearer example"})).json() == {
                "call": 3
            }
        assert app.state.telemetry_route_cache.statistics()["hits"] == 2
        spans = [s for s in exporter.get_finished_spans() if s.kind == SpanKind.SERVER]
        assert len(spans) == 3 and len({s.context.span_id for s in spans}) == 3
        assert all(
            s.name == "GET /secure" and s.attributes["http.route"] == "/secure" for s in spans
        )
        data = reader.get_metrics_data()
        assert data is not None
        duration_counts = [
            sum(point.count for point in metric.data.data_points)
            for resource in data.resource_metrics
            for instrumentation in resource.scope_metrics
            for metric in instrumentation.metrics
            if metric.name in {"http.server.duration", "http.server.request.duration"}
        ]
        assert duration_counts and all(count == 3 for count in duration_counts)
    finally:
        tracer.shutdown()
        meter.shutdown()


async def test_nested_router_updates_invalidate(
    providers: tuple[TracerProvider, MeterProvider],
) -> None:
    app = FastAPI()
    child = APIRouter()

    @child.get("/one")
    async def one() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(child, prefix="/api")
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=providers[0], meter_provider=providers[1]
    )
    assert install_static_route_span_cache(app, max_entries=8, max_key_chars=2048)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        await c.get("/api/one")
        await c.get("/api/one")
        cache = app.state.telemetry_route_cache
        assert cache.statistics()["hits"] == 1
        child.add_api_route("/two", one, methods=["GET"])
        assert (await c.get("/api/two")).status_code == 200
        assert cache.statistics()["entries"] == 1


async def test_same_length_root_route_replacement_invalidate(
    providers: tuple[TracerProvider, MeterProvider],
) -> None:
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

    @app.get("/one")
    async def one() -> dict[str, bool]:
        return {"ok": True}

    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=providers[0], meter_provider=providers[1]
    )
    assert install_static_route_span_cache(app, max_entries=8, max_key_chars=2048)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        await c.get("/one")
        await c.get("/one")
        cache = app.state.telemetry_route_cache
        assert cache.statistics()["hits"] == 1
        app.router.routes[0] = Route("/other", one)
        assert len(app.router.routes) == 1
        assert (await c.get("/one")).status_code == 404
        assert cache.statistics()["entries"] == 0


def test_unsupported_router_and_disabled_cache_leave_stack_unchanged() -> None:
    app = SimpleNamespace(router=SimpleNamespace(routes=[]), build_middleware_stack=lambda: None)
    original = app.build_middleware_stack
    assert not install_static_route_span_cache(app, max_entries=8, max_key_chars=2048)
    assert not install_static_route_span_cache(app, max_entries=0, max_key_chars=2048)
    assert app.build_middleware_stack is original
