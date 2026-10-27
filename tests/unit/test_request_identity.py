"""Request-local identity reuse must not weaken revocation or leak into child jobs."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cygnusx.api import deps
from cygnusx.application.services.request_identity import (
    load_request_identity,
    request_identity_scope,
)
from cygnusx.core.exceptions import AuthenticationError
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.middleware.module_gate import ModuleGateMiddleware

pytestmark = pytest.mark.unit


class IdentityStore:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.user: UserModel | None = UserModel(
            id=self.user_id, role="user", status="active", token_version=0, disabled_modules=[]
        )
        self.calls = 0
        self.fail_next = False

    def __call__(self) -> IdentitySession:
        return IdentitySession(self)

    @property
    def factory(self) -> async_sessionmaker[AsyncSession]:
        return cast(async_sessionmaker[AsyncSession], self)


class IdentitySession:
    def __init__(self, store: IdentityStore) -> None:
        self.store = store

    async def __aenter__(self) -> IdentitySession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def get(self, model: type[UserModel], key: UUID) -> UserModel | None:
        self.store.calls += 1
        await asyncio.sleep(0)
        if self.store.fail_next:
            self.store.fail_next = False
            raise RuntimeError("test database failure")
        return self.store.user if key == self.store.user_id else None


async def test_same_request_uses_one_query_even_with_parallel_dependents() -> None:
    store = IdentityStore()
    with request_identity_scope():
        identities = await asyncio.gather(
            *(load_request_identity(store.user_id, store.factory) for _ in range(10))
        )
    assert store.calls == 1
    assert all(user is identities[0] for user in identities)


async def test_no_cache_outside_request_scope() -> None:
    store = IdentityStore()
    for _ in range(2):
        await load_request_identity(store.user_id, store.factory)
    assert store.calls == 2


async def test_simultaneous_requests_never_share_their_query() -> None:
    store = IdentityStore()

    async def request() -> None:
        with request_identity_scope():
            await load_request_identity(store.user_id, store.factory)

    await asyncio.gather(request(), request())
    assert store.calls == 2


async def test_different_user_ids_do_not_reuse_another_identity() -> None:
    store = IdentityStore()
    with request_identity_scope():
        assert await load_request_identity(store.user_id, store.factory) is not None
        assert await load_request_identity(uuid4(), store.factory) is None
    assert store.calls == 2


async def test_different_database_factories_do_not_share_a_snapshot() -> None:
    first_store = IdentityStore()
    second_store = IdentityStore()
    second_store.user_id = first_store.user_id
    assert second_store.user is not None
    second_store.user.id = second_store.user_id
    second_store.user.status = "locked"
    with request_identity_scope():
        first = await load_request_identity(first_store.user_id, first_store.factory)
        second = await load_request_identity(second_store.user_id, second_store.factory)
    assert first is not None and first.status == "active"
    assert second is not None and second.status == "locked"
    assert first_store.calls == second_store.calls == 1


async def test_next_request_sees_disabled_account_and_module_changes() -> None:
    store = IdentityStore()
    with request_identity_scope():
        first = await load_request_identity(store.user_id, store.factory)
    assert store.user is not None
    store.user.status = "inactive"
    store.user.token_version = 1
    store.user.disabled_modules.append("ai-assistant")
    with request_identity_scope():
        second = await load_request_identity(store.user_id, store.factory)
    assert first is not None and second is not None
    assert first.status == "active" and first.disabled_modules == frozenset()
    assert second.status == "inactive" and second.token_version == 1
    assert second.disabled_modules == frozenset({"ai-assistant"})
    assert store.calls == 2


async def test_background_child_rechecks_after_response_headers() -> None:
    store = IdentityStore()
    continue_child = asyncio.Event()

    async def delayed_identity() -> str:
        await continue_child.wait()
        identity = await load_request_identity(store.user_id, store.factory)
        assert identity is not None
        return identity.status

    with request_identity_scope():
        await load_request_identity(store.user_id, store.factory)
        task = asyncio.create_task(delayed_identity())
    assert store.user is not None
    store.user.status = "locked"
    continue_child.set()
    assert await task == "locked"
    assert store.calls == 2


async def test_copied_thread_context_does_not_share_an_event_loop_cache() -> None:
    store = IdentityStore()
    with request_identity_scope():
        first = await load_request_identity(store.user_id, store.factory)
        assert first is not None and first.status == "active"
        assert store.user is not None
        store.user.status = "locked"

        def in_another_loop() -> str:
            async def load() -> str:
                identity = await load_request_identity(store.user_id, store.factory)
                assert identity is not None
                return identity.status

            return asyncio.run(load())

        assert await asyncio.to_thread(in_another_loop) == "locked"
    assert store.calls == 2


async def test_errors_are_not_cached_and_can_recover() -> None:
    store = IdentityStore()
    store.fail_next = True
    with request_identity_scope():
        with pytest.raises(RuntimeError, match="database failure"):
            await load_request_identity(store.user_id, store.factory)
        assert await load_request_identity(store.user_id, store.factory) is not None
    assert store.calls == 2


@pytest.fixture
def jwt_store(monkeypatch: pytest.MonkeyPatch) -> IdentityStore:
    store = IdentityStore()
    monkeypatch.setattr(deps, "get_session_factory", lambda: store.factory)
    monkeypatch.setattr(
        "cygnusx.infrastructure.database.session.get_session_factory", lambda: store.factory
    )
    monkeypatch.setattr(
        deps,
        "decode_token",
        lambda token: {
            "sub": str(store.user_id),
            "type": "access",
            "token_version": int(token),
        },
    )
    return store


async def test_module_gate_and_jwt_validate_one_database_snapshot(jwt_store: IdentityStore) -> None:
    with request_identity_scope():
        assert not await ModuleGateMiddleware._is_module_blocked(str(jwt_store.user_id), "tools")
        assert await deps._authenticate_jwt("0") == str(jwt_store.user_id)
    assert jwt_store.calls == 1


async def test_cached_identity_does_not_skip_token_version_validation(
    jwt_store: IdentityStore,
) -> None:
    with request_identity_scope():
        await ModuleGateMiddleware._is_module_blocked(str(jwt_store.user_id), "tools")
        with pytest.raises(AuthenticationError, match="令牌已失效"):
            await deps._authenticate_jwt("1")
    assert jwt_store.calls == 1


async def test_revocation_is_seen_on_the_next_request(jwt_store: IdentityStore) -> None:
    with request_identity_scope():
        await deps._authenticate_jwt("0")
    assert jwt_store.user is not None
    jwt_store.user.token_version = 1
    with request_identity_scope(), pytest.raises(AuthenticationError, match="令牌已失效"):
        await deps._authenticate_jwt("0")
    assert jwt_store.calls == 2


@pytest.mark.parametrize("missing", [True, False])
async def test_missing_or_disabled_user_is_rejected(
    jwt_store: IdentityStore, missing: bool
) -> None:
    if missing:
        jwt_store.user = None
    else:
        assert jwt_store.user is not None
        jwt_store.user.status = "locked"
    with (
        request_identity_scope(),
        pytest.raises(AuthenticationError, match="用户不存在或已被禁用"),
    ):
        await deps._authenticate_jwt("0")
