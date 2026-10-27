"""Reuse an identity until the current HTTP response headers are produced.

The cache is created by ModuleGate, inherited by downstream request tasks, and
invalidated when the middleware returns. It is never shared across requests/factories/loops or
retained by background/streaming tasks after response headers have been produced.
JWT decoding and token-version checks remain the caller's responsibility.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cygnusx.infrastructure.database.models.user import UserModel


@dataclass(frozen=True)
class RequestIdentity:
    user_id: UUID
    role: str
    status: str
    token_version: int
    disabled_modules: frozenset[str]


@dataclass
class _IdentityCache:
    users: dict[tuple[async_sessionmaker[AsyncSession], UUID], RequestIdentity | None] = field(
        default_factory=dict
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    loop: asyncio.AbstractEventLoop = field(default_factory=asyncio.get_running_loop)
    active: bool = True


_identity_cache: ContextVar[_IdentityCache | None] = ContextVar("request_identity", default=None)


@contextmanager
def request_identity_scope() -> Iterator[None]:
    cache = _IdentityCache()
    token = _identity_cache.set(cache)
    try:
        yield
    finally:
        # Child tasks inherit a reference. Invalidate that reference as well as
        # resetting our ContextVar, so delayed work must re-read the database.
        cache.active = False
        cache.users.clear()
        _identity_cache.reset(token)


async def _load_identity(
    user_id: UUID, session_factory: async_sessionmaker[AsyncSession]
) -> RequestIdentity | None:
    async with session_factory() as session:
        user = await session.get(UserModel, user_id)
        if user is None:
            return None
        return RequestIdentity(
            user_id=user_id,
            role=user.role,
            status=user.status,
            token_version=user.token_version,
            disabled_modules=frozenset(user.disabled_modules or []),
        )


async def load_request_identity(
    user_id: UUID, session_factory: async_sessionmaker[AsyncSession]
) -> RequestIdentity | None:
    cache = _identity_cache.get()
    if cache is None or not cache.active or cache.loop is not asyncio.get_running_loop():
        return await _load_identity(user_id, session_factory)
    key = (session_factory, user_id)
    async with cache.lock:
        if not cache.active:
            return await _load_identity(user_id, session_factory)
        if key not in cache.users:
            identity = await _load_identity(user_id, session_factory)
            if cache.active:
                cache.users[key] = identity
            return identity
        return cache.users[key]
