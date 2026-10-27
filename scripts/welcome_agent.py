#!/usr/bin/env python3
"""Run an offline welcome job with the normal Settings/provider/Agent runtime.

Examples (use an isolated DB for rehearsals):
  uv run python scripts/welcome_agent.py generate --week 2026-11-02 --audience admin
  uv run python scripts/welcome_agent.py reconcile
Production uses Celery; this direct entry is for controlled maintenance/rehearsals.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date

from cygnusx.application.services.welcome.generation import generate_batch
from cygnusx.infrastructure.celery_app.tasks.welcome import reconcile_async
from loguru import logger


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--week", type=date.fromisoformat, required=True)
    generate.add_argument("--audience", choices=["admin", "general"], required=True)
    generate.add_argument("--revision", type=int, default=1)
    commands.add_parser("reconcile")
    args = parser.parse_args()
    if args.command == "generate":
        result = await generate_batch(args.week, args.audience, args.revision)
    else:
        result = await reconcile_async()
    logger.info("Welcome maintenance result: {}", result)


if __name__ == "__main__":
    asyncio.run(main())
