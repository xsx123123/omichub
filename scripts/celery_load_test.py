"""Bounded synthetic Celery probe on the configured broker, using a private queue.

Run inside the deployment container, from /app:
python -m scripts.celery_load_test --output /tmp/celery-capacity.json
No analysis task is submitted; production workers never consume the probe queue.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from celery import Celery
from cygnusx.core.config import get_settings
from redis import Redis
from scripts.web_load_test import percentile

settings = get_settings()
app = Celery(
    "web_capacity_probe", broker=settings.celery_broker_url, backend=settings.celery_result_backend
)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10,
    task_track_started=True,
    result_expires=600,
)


@app.task(name="web_capacity_probe.noop")  # type: ignore[untyped-decorator]
def noop(published: float) -> dict[str, float]:
    """10 ms of synthetic work, with timestamps to separate wait from execution."""
    started = time.time()
    time.sleep(0.01)
    return {"published": published, "started": started, "finished": time.time()}


def run_stage(
    queue: str, users: int, tasks_per_user: int, *, production_builtin: bool = False
) -> dict[str, Any]:
    waiting: list[float] = []
    service: list[float] = []
    elapsed: list[float] = []
    errors: list[str] = []
    depths: list[int] = []
    stop = threading.Event()

    def monitor() -> None:
        with Redis.from_url(settings.celery_broker_url) as client:
            # Kombu Redis priority bins (default transport options).
            keys = [queue, *(f"{queue}\x06\x16{p}" for p in (3, 6, 9))]
            while not stop.is_set():
                depths.append(sum(client.llen(key) for key in keys))
                stop.wait(0.1)

    def producer(_: int) -> None:
        for _ in range(tasks_per_user):
            before = time.perf_counter()
            result = None
            try:
                result = (
                    app.send_task("celery.accumulate", args=[1], queue=queue)
                    if production_builtin
                    else noop.apply_async(args=[time.time()], queue=queue)
                )
                # Poll Redis metadata explicitly. Redis pubsub result consumers can
                # block when many calling threads share Celery state; do not make
                # that client-side wait appear to be a Worker execution failure.
                deadline = time.monotonic() + 60
                while True:
                    meta = app.backend.get_task_meta(result.id)
                    if meta["status"] == "SUCCESS":
                        value = meta["result"]
                        break
                    if meta["status"] in {"FAILURE", "REVOKED"}:
                        raise RuntimeError(f"Task terminal status: {meta['status']}")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Probe task did not finish in 60 seconds")
                    time.sleep(0.01)
                if production_builtin:
                    if value != [1]:
                        raise ValueError("Unexpected builtin task result")
                else:
                    waiting.append((value["started"] - value["published"]) * 1000)
                    service.append((value["finished"] - value["started"]) * 1000)
                elapsed.append((time.perf_counter() - before) * 1000)
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                if result is not None:
                    result.forget()

    sampler = threading.Thread(target=monitor, daemon=True)
    sampler.start()
    before = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=users) as pool:
            list(pool.map(producer, range(users)))
    finally:
        stop.set()
        sampler.join(timeout=5)
    wall = time.perf_counter() - before
    return {
        "users": users,
        "submitted": users * tasks_per_user,
        "completed": len(elapsed),
        "errors": errors,
        "elapsed_s": round(wall, 3),
        "completed_tasks_per_s": round(len(elapsed) / wall, 2),
        "end_to_end_p95_ms": percentile(elapsed, 0.95),
        "publish_to_start_p95_ms": percentile(waiting, 0.95) if waiting else None,
        "service_p95_ms": percentile(service, 0.95) if service else None,
        "max_sampled_queue_depth": max(depths, default=0),
    }


def main(args: argparse.Namespace) -> int:
    if args.production_builtin:
        return run_production(args)
    run_id = uuid.uuid4().hex[:12]
    queue = f"webperf_{run_id}"
    hostname = f"webperf_{run_id}@capacity"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "queue": queue,
        "worker_concurrency": args.worker_concurrency,
        "prefetch_multiplier": 1,
        "max_tasks_per_child": args.max_tasks_per_child,
        "synthetic_service_ms": 10,
        "stages": [],
        "scope": "synthetic broker/worker/result round trip, excludes Web submission and business tasks",
    }
    worker: subprocess.Popen[bytes] | None = None
    try:
        with args.output.with_suffix(".worker.log").open("wb") as log:
            worker = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "celery",
                    "-A",
                    "scripts.celery_load_test:app",
                    "worker",
                    "--queues",
                    queue,
                    "--hostname",
                    hostname,
                    "--concurrency",
                    str(args.worker_concurrency),
                    "--max-tasks-per-child",
                    str(args.max_tasks_per_child),
                    "--loglevel",
                    "WARNING",
                    "--without-gossip",
                    "--without-mingle",
                    "--without-heartbeat",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            ready = False
            for _ in range(20):
                if worker.poll() is not None:
                    raise RuntimeError("Probe worker exited before ready; inspect worker log")
                if app.control.ping(destination=[hostname], timeout=1):
                    ready = True
                    break
            if not ready:
                raise RuntimeError("Probe worker did not become ready")
            for users in args.users:
                result = run_stage(queue, users, args.tasks_per_user)
                report["stages"].append(result)
                args.output.write_text(json.dumps(report, indent=2) + "\n")
                logging.info(
                    "users=%s completed_per_s=%s wait_p95_ms=%s errors=%s",
                    users,
                    result["completed_tasks_per_s"],
                    result["publish_to_start_p95_ms"],
                    len(result["errors"]),
                )
    finally:
        if worker is not None and worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=30)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
        # Only remove this run's own empty queue/bindings. Never purge shared queues.
        with app.connection() as connection:
            channel = connection.channel()
            channel.queue_delete(queue, if_empty=True)
        app.close()
    report["worker_stopped"] = worker is not None and worker.poll() is not None
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 1 if any(s["errors"] for s in report["stages"]) else 0


def run_production(args: argparse.Namespace) -> int:
    """Exercise existing Worker processes with Celery's side-effect-free builtin task."""
    inspector = app.control.inspect(timeout=3)
    queues = inspector.active_queues() or {}
    nodes = [
        node for node, entries in queues.items() if any(q["name"] == "analysis" for q in entries)
    ]
    replies = (
        app.control.broadcast(
            "registered", arguments={"builtins": True}, destination=nodes, reply=True, timeout=3
        )
        if nodes
        else []
    )
    registered = {node: entries for reply in replies for node, entries in reply.items()}
    if (
        not nodes
        or not registered
        or any("celery.accumulate" not in entries for entries in registered.values())
    ):
        raise RuntimeError("Existing analysis Worker must register celery.accumulate")
    stats = app.control.inspect(destination=nodes, timeout=3).stats() or {}
    report: dict[str, Any] = {
        "queue": "analysis",
        "task": "celery.accumulate(1)",
        "worker_concurrency": {
            n: s.get("pool", {}).get("max-concurrency") for n, s in stats.items()
        },
        "scope": "existing production Worker builtin no-op round trip; excludes HTTP and business work",
        "queue_depth_scope": "shared analysis queue, includes unrelated tasks",
        "stages": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for users in args.users:
            result = run_stage("analysis", users, args.tasks_per_user, production_builtin=True)
            report["stages"].append(result)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            logging.info(
                "production users=%s completed_per_s=%s errors=%s",
                users,
                result["completed_tasks_per_s"],
                len(result["errors"]),
            )
    finally:
        # Shared queue and existing Worker lifecycle are never modified.
        app.close()
    return 1 if any(s["errors"] for s in report["stages"]) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--users", type=int, nargs="+", default=[10, 20, 50, 100])
    parser.add_argument("--tasks-per-user", type=int, default=10)
    parser.add_argument("--worker-concurrency", type=int, default=4)
    parser.add_argument(
        "--max-tasks-per-child",
        type=int,
        default=10,
        help="Temporary Worker only; production Worker is not reconfigured",
    )
    parser.add_argument(
        "--production-builtin",
        action="store_true",
        help="Use existing analysis Worker and Celery builtin no-op",
    )
    options = parser.parse_args()
    if (
        min(options.users) < 1
        or options.tasks_per_user < 1
        or options.worker_concurrency < 1
        or options.max_tasks_per_child < 1
    ):
        parser.error("counts must be positive")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main(options))
