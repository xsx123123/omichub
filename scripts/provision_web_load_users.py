"""Provision/revoke disposable read-only workload identities inside the Web container.

Uses the deployment's DB and signing configuration; never copies secrets out.
The manifest contains short-lived JWTs: store it privately and delete after cleanup.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
from datetime import timedelta
from pathlib import Path

from cygnusx.core.security import create_access_token, hash_password
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.database.session import get_engine, get_session_factory
from sqlalchemy import delete, select


async def main(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"webperf_[a-z0-9_]{8,40}", args.prefix):
        raise ValueError("Use a unique webperf_ prefix followed by 8-40 lowercase characters")
    factory = get_session_factory()
    marker = f"Disposable Web load test: {args.prefix}"
    async with factory() as db:
        existing = list(
            (
                await db.scalars(
                    select(UserModel).where(
                        UserModel.username.startswith(args.prefix + "_", autoescape=True)
                    )
                )
            ).all()
        )
        if args.cleanup:
            if any(user.admin_note != marker or user.role != "user" for user in existing):
                raise ValueError("Refusing cleanup of users not owned by this run")
            ids = [user.id for user in existing]
            if ids:
                await db.execute(delete(UserModel).where(UserModel.id.in_(ids)))
                await db.commit()
            args.output.unlink(missing_ok=True)
        else:
            if existing or args.output.exists():
                raise ValueError("Run prefix/output already exists; choose a fresh run ID")
            password_hash = hash_password(secrets.token_urlsafe(40))
            users = [
                UserModel(
                    username=f"{args.prefix}_{i:03}",
                    email=f"{args.prefix}_{i:03}@example.invalid",
                    hashed_password=password_hash,
                    role="user",
                    status="active",
                    token_version=0,
                    admin_note=marker,
                    storage_quota=0,
                )
                for i in range(args.count)
            ]
            db.add_all(users)
            await db.flush()
            tokens = [
                create_access_token(
                    str(user.id),
                    token_version=0,
                    expires_delta=timedelta(minutes=args.ttl_minutes),
                )
                for user in users
            ]
            # Write before commit: an output failure rolls back the database transaction.
            with open(
                args.output, "x", opener=lambda path, flags: os.open(path, flags, 0o600)
            ) as handle:
                json.dump(tokens, handle)
            await db.commit()
    await get_engine().dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--ttl-minutes", type=int, default=30)
    options = parser.parse_args()
    if not 1 <= options.count <= 1000:
        parser.error("count must be 1..1000")
    if not 1 <= options.ttl_minutes <= 240:
        parser.error("ttl-minutes must be 1..240")
    asyncio.run(main(options))
