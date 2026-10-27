"""Bounded caching of static OTel route labels; never cache routing or responses."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from threading import RLock
from typing import Any, cast

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Scope

SpanDetails = tuple[str, dict[str, Any]]


class StaticRouteSpanDetails:
    """Cache only the standard static-route name/attribute pair for one app.

    Missing/unsupported route versions, dynamic paths, custom attributes and
    oversized keys use the original resolver. Returned attributes are copied so
    one request cannot change another request's telemetry.
    """

    def __init__(
        self,
        app: Any,
        resolver: Callable[[Scope], SpanDetails],
        version: Callable[[], object],
        literal_paths: Callable[[], set[str]],
        *,
        max_entries: int,
        max_key_chars: int,
    ) -> None:
        self.app = app
        self.resolver = resolver
        self.version = version
        self.literal_paths = literal_paths
        self.max_entries = max_entries
        self.max_key_chars = max_key_chars
        self._entries: OrderedDict[tuple[Any, ...], SpanDetails] = OrderedDict()
        self._version: object = object()
        self._literal_paths: set[str] = set()
        self._lock = RLock()
        self.hits = 0
        self.misses = 0

    def __call__(self, scope: Scope) -> SpanDetails:
        if self.max_entries <= 0 or scope["type"] != "http" or scope.get("app") is not self.app:
            return self.resolver(scope)
        method = scope.get("method", "")
        path = scope.get("path", "")
        root = scope.get("root_path", "")
        host = Headers(scope=scope).get("host", "")
        if len(method) + len(path) + len(root) + len(host) > self.max_key_chars:
            return self.resolver(scope)
        server = scope.get("server")
        key = (method, path, root, host, scope.get("scheme"), tuple(server) if server else None)
        with self._lock:
            try:
                version = self.version()
            except Exception:
                return self.resolver(scope)
            if version != self._version:
                self._entries.clear()
                try:
                    self._literal_paths = self.literal_paths()
                except Exception:
                    self._literal_paths.clear()
                    return self.resolver(scope)
                self._version = version
            if path not in self._literal_paths:
                return self.resolver(scope)
            if key in self._entries:
                self.hits += 1
                self._entries.move_to_end(key)
                name, attributes = self._entries[key]
                return name, attributes.copy()
            self.misses += 1
            name, attributes = self.resolver(scope)
            # No unknown URLs, path-parameter values, or request-specific tags
            # are retained. Noncanonical methods also use the original resolver.
            if attributes == {"http.route": path} and name == f"{method} {path}":
                self._entries[key] = (name, attributes.copy())
                self._entries.move_to_end(key)
                while len(self._entries) > self.max_entries:
                    self._entries.popitem(last=False)
            return name, attributes

    def statistics(self) -> dict[str, int]:
        with self._lock:
            return {"hits": self.hits, "misses": self.misses, "entries": len(self._entries)}


def install_static_route_span_cache(app: Any, *, max_entries: int, max_key_chars: int) -> bool:
    """Keep the official instrumentation stack and wrap its metadata callback.

    The FastAPI route-version API is feature-detected. On older or unsupported
    frameworks no cache is installed; traces and requests keep their old path.
    """
    if max_entries <= 0:
        return False
    router = app.router
    read_version = getattr(router, "_get_routes_version", None)
    if not callable(read_version):
        return False
    try:
        from fastapi.routing import APIRoute, APIWebSocketRoute, iter_route_contexts
    except ImportError:
        return False
    from starlette.routing import Host, Mount, Route, WebSocketRoute

    build_stack = app.build_middleware_stack
    if getattr(build_stack, "_cygnusx_route_cache_hook", False):
        return False
    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

    def route_version() -> object:
        version = read_version()
        if not isinstance(version, int):
            raise TypeError("Unsupported FastAPI route version")
        return version, tuple(id(route) for route in router.routes)

    def literal_paths() -> set[str]:
        paths: set[str] = set()
        for context in iter_route_contexts(router.routes):
            route = getattr(context, "original_route", context)
            if type(route) not in (APIRoute, APIWebSocketRoute, Route, WebSocketRoute, Mount, Host):
                # A custom matcher may depend on arbitrary request headers.
                return set()
            path = getattr(context, "path", None)
            if type(route) in (APIRoute, Route) and isinstance(path, str) and "{" not in path:
                paths.add(path)
        return paths

    @wraps(build_stack)
    def build_with_cache() -> ASGIApp:
        stack: ASGIApp = build_stack()
        node: Any = stack
        seen: set[int] = set()
        while node is not None and id(node) not in seen:
            seen.add(id(node))
            if isinstance(node, OpenTelemetryMiddleware):
                resolver = node.default_span_details
                if (
                    getattr(resolver, "__module__", "") == "opentelemetry.instrumentation.fastapi"
                    and getattr(resolver, "__name__", "") == "_get_default_span_details"
                ):
                    cache = StaticRouteSpanDetails(
                        app,
                        cast(Callable[[Scope], SpanDetails], resolver),
                        route_version,
                        literal_paths,
                        max_entries=max_entries,
                        max_key_chars=max_key_chars,
                    )
                    node.default_span_details = cache
                    app.state.telemetry_route_cache = cache
                break
            node = getattr(node, "app", None)
        return stack

    setattr(build_with_cache, "_cygnusx_route_cache_hook", True)  # noqa: B010
    app.build_middleware_stack = build_with_cache
    return True
