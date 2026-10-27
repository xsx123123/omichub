"""Isolated HTTP-capacity server using real routes and middleware.

Run inside the Web deployment container on a separate, unpublished port. This
replaces only startup/shutdown jobs: no migrations, seed writes, Provider probes,
sandbox warmup or scheduled tasks. Request handlers and authorization are real.
Never use this entry point to serve production traffic.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import os
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

import uvicorn
from cygnusx.core.config import get_settings
from cygnusx.core.logging import setup_logging
from cygnusx.core.telemetry import setup_telemetry
from cygnusx.infrastructure.config.module_registry import init_module_registry
from cygnusx.infrastructure.database.session import close_db, get_engine, init_db
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.engine import Connection


@asynccontextmanager
async def capacity_lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    setup_telemetry("web")
    init_module_registry()
    await init_db()
    try:
        yield
    finally:
        await close_db()


def main(args: argparse.Namespace) -> None:
    if not 18000 <= args.port <= 18999:
        raise ValueError("Use a separate unpublished capacity-test port in 18000..18999")
    if get_settings().service_name != "web":
        raise ValueError("SERVICE_NAME must be web so the real async connection pool is used")
    from cygnusx.main import app

    if args.disable_request_identity_cache:
        from cygnusx.middleware import module_gate

        @contextmanager
        def uncached_identity_scope() -> Iterator[None]:
            yield

        module_gate.request_identity_scope = uncached_identity_scope

    if args.legacy_wrappers:
        # Reproduce the inherited implementation used before the inactive-path
        # fast paths, without changing files under the running production app.
        from cygnusx.middleware.audit import AuditMiddleware
        from cygnusx.middleware.cookie import CookieRequiredMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware

        AuditMiddleware.__call__ = BaseHTTPMiddleware.__call__  # type: ignore[method-assign]
        CookieRequiredMiddleware.__call__ = BaseHTTPMiddleware.__call__  # type: ignore[method-assign]

    if args.manifest:
        from cygnusx.middleware.audit import AuditMiddleware
        from cygnusx.middleware.cookie import CookieRequiredMiddleware

        settings = get_settings()
        args.manifest.write_text(
            json.dumps(
                {
                    "port": args.port,
                    "pid": os.getpid(),
                    "app_debug": settings.app_debug,
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow,
                    "legacy_wrappers": args.legacy_wrappers,
                    "request_identity_cache": not args.disable_request_identity_cache,
                    "telemetry_route_cache_size": settings.telemetry_route_cache_size,
                    "audit_call": AuditMiddleware.__call__.__qualname__,
                    "cookie_call": CookieRequiredMiddleware.__call__.__qualname__,
                    "lifecycle": "read-only capacity startup; real routes and request middleware",
                },
                indent=2,
            )
            + "\n"
        )

    app.router.lifespan_context = capacity_lifespan
    config = uvicorn.Config(app, host=args.host, port=args.port, access_log=False)
    server = uvicorn.Server(config)
    queries = {"selects": 0, "users_selects": 0}
    if args.query_stats:

        def record_query(
            _connection: Connection,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            sql = statement.lower().lstrip()
            if sql.startswith("select"):
                queries["selects"] += 1
                if "from users" in sql or 'from "users"' in sql:
                    queries["users_selects"] += 1

        event.listen(get_engine().sync_engine, "after_cursor_execute", record_query)
    if args.stop_after:
        timer = threading.Timer(args.stop_after, setattr, args=(server, "should_exit", True))
        timer.daemon = True
        timer.start()
    try:
        if args.profile:
            profiler = cProfile.Profile()
            try:
                profiler.runcall(server.run)
            finally:
                args.profile.parent.mkdir(parents=True, exist_ok=True)
                profiler.dump_stats(str(args.profile))
        else:
            server.run()
    finally:
        if args.query_stats:
            statistics: dict[str, Any] = dict(queries)
            statistics["completed_http_requests"] = server.server_state.total_requests
            route_cache = getattr(app.state, "telemetry_route_cache", None)
            statistics["telemetry_route_cache"] = (
                route_cache.statistics() if route_cache is not None else None
            )
            args.query_stats.write_text(json.dumps(statistics, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18001)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--legacy-wrappers", action="store_true")
    parser.add_argument("--disable-request-identity-cache", action="store_true")
    parser.add_argument("--query-stats", type=Path)
    parser.add_argument(
        "--stop-after",
        type=float,
        default=0,
        help="Gracefully stop after this many seconds, excluding import time",
    )
    main(parser.parse_args())
