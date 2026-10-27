"""Real HTTP closed-loop Web load test; no sandbox or LLM calls.

Run with uv run --frozen python scripts/web_load_test.py --help.
Tokens are read from a private JSON list, never included in results.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import random
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

PROFILES = {
    "business": [
        "/api/v1/auth/me",
        "/api/v1/projects",
        "/api/v1/tasks?limit=20",
        "/api/v1/chat/sessions",
        "/api/v1/modules/registry",
    ],
    "public": ["/api/v1/site-settings", "/api/v1/site-content"],
    "static": ["/"],
    "health": ["/health"],
}


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * quantile) - 1)], 2)


async def run_stage(
    args: argparse.Namespace, tokens: list[str], users: int, duration: float
) -> dict[str, Any]:
    codes: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    latencies: list[float] = []
    successful: list[float] = []
    endpoints: dict[str, list[float]] = defaultdict(list)
    endpoint_codes: dict[str, Counter[str]] = defaultdict(Counter)
    started = time.perf_counter()
    deadline = started + duration
    lag: list[float] = []

    async def observe_lag() -> None:
        while time.perf_counter() < deadline:
            before = time.perf_counter()
            await asyncio.sleep(0.1)
            lag.append(max(0, (time.perf_counter() - before - 0.1) * 1000))

    connector = aiohttp.TCPConnector(limit=users, limit_per_host=users)
    timeout = aiohttp.ClientTimeout(total=args.timeout)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

        async def virtual_user(index: int) -> None:
            rng = random.Random(index)
            headers = {"User-Agent": "CygnusX-Web-LoadTest/1"}
            if tokens:
                headers["Authorization"] = f"Bearer {tokens[index]}"
            sequence = index
            while time.perf_counter() < deadline:
                path = args.paths[sequence % len(args.paths)]
                sequence += 1
                before = time.perf_counter()
                code = "transport_error"
                valid = False
                try:
                    async with session.get(
                        args.base_url.rstrip("/") + path,
                        headers=headers,
                        allow_redirects=False,
                    ) as response:
                        body = await response.read()
                        code = str(response.status)
                        valid = response.status == 200
                        if valid and args.profile != "static":
                            try:
                                payload = json.loads(body)
                                valid = isinstance(payload, (list, dict))
                                if isinstance(payload, dict) and "detail" in payload:
                                    valid = False
                            except (ValueError, UnicodeDecodeError):
                                valid = False
                        if not valid:
                            errors[code if response.status != 200 else "invalid_body"] += 1
                except (aiohttp.ClientError, TimeoutError) as exc:
                    errors[type(exc).__name__] += 1
                elapsed = (time.perf_counter() - before) * 1000
                codes[code] += 1
                latencies.append(elapsed)
                endpoints[path].append(elapsed)
                endpoint_codes[path][code] += 1
                if valid:
                    successful.append(elapsed)
                if args.think_time:
                    remaining = deadline - time.perf_counter()
                    await asyncio.sleep(
                        max(0, min(remaining, args.think_time * rng.uniform(0.5, 1.5)))
                    )

        await asyncio.gather(observe_lag(), *(virtual_user(i) for i in range(users)))
    wall = time.perf_counter() - started
    return {
        "users": users,
        "requested_duration_s": duration,
        "elapsed_s": round(wall, 3),
        "requests": len(latencies),
        "successful_requests": len(successful),
        "rps": round(len(latencies) / wall, 2),
        "successful_rps": round(len(successful) / wall, 2),
        "error_rate": round(sum(errors.values()) / max(1, len(latencies)), 6),
        "statuses": dict(codes),
        "errors": dict(errors),
        "latency_ms": {
            "p50": percentile(latencies, 0.5),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
            "max": round(max(latencies, default=0), 2),
        },
        "successful_latency_ms": {
            "p50": percentile(successful, 0.5),
            "p95": percentile(successful, 0.95),
            "p99": percentile(successful, 0.99),
        },
        "generator_event_loop_lag_p99_ms": percentile(lag, 0.99),
        "endpoints": {
            path: {
                "requests": len(values),
                "p95_ms": percentile(values, 0.95),
                "statuses": dict(endpoint_codes[path]),
            }
            for path, values in endpoints.items()
        },
    }


async def main(args: argparse.Namespace) -> int:
    tokens = json.loads(args.tokens_file.read_text()) if args.tokens_file else []
    if args.profile == "business" and len(tokens) < max(args.users):
        raise ValueError("Business profile requires one distinct test token per virtual user")
    if tokens and len(set(tokens)) != len(tokens):
        raise ValueError("Use distinct test accounts/tokens")
    args.paths = args.path or PROFILES[args.profile]
    report: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "profile": args.profile,
        "paths": args.paths,
        "think_time_s": args.think_time,
        "warmup_s": args.warmup,
        "timeout_s": args.timeout,
        "criteria": {"max_error_rate": args.max_error_rate, "max_p95_ms": args.max_p95_ms},
        "model": "closed-loop: one outstanding request per virtual user",
        "stages": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.warmup:
        await run_stage(args, tokens, min(args.users), args.warmup)
    for users in args.users:
        logging.info("Starting %s users for %ss", users, args.duration)
        result = await run_stage(args, tokens, users, args.duration)
        result["passed"] = (
            result["error_rate"] <= args.max_error_rate
            and result["successful_requests"] > 0
            and result["successful_latency_ms"]["p95"] <= args.max_p95_ms
        )
        report["stages"].append(result)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        logging.info(
            "users=%s good_rps=%s p95_ms=%s error_rate=%s",
            users,
            result["successful_rps"],
            result["successful_latency_ms"]["p95"],
            result["error_rate"],
        )
    return 0 if all(s["passed"] for s in report["stages"]) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--profile", choices=PROFILES, default="business")
    parser.add_argument("--tokens-file", type=Path)
    parser.add_argument("--users", type=int, nargs="+", default=[10, 20, 50, 100])
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--warmup", type=float, default=5)
    parser.add_argument("--think-time", type=float, default=1)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--path", action="append")
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    parsed = parser.parse_args()
    if min(parsed.users) < 1 or parsed.duration <= 0 or parsed.think_time < 0:
        parser.error("users/duration must be positive and think-time non-negative")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(asyncio.run(main(parsed)))
