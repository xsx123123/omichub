"""共享 LLM 出站 httpx client 的单元测试。

覆盖 shared_http._SharedClientHolder 的按事件循环缓存语义：
同一循环复用同一 client，切换循环后重建。
"""

import asyncio

import httpx
import pytest

from cygnusx.infrastructure.ai_provider.shared_http import (
    _SharedClientHolder,
    get_shared_llm_http_client,
)


@pytest.mark.unit
async def test_holder_returns_same_client_within_loop() -> None:
    holder = _SharedClientHolder()
    first = holder.get()
    second = holder.get()
    assert first is second
    assert isinstance(first, httpx.AsyncClient)
    await first.aclose()


@pytest.mark.unit
def test_holder_rebuilds_client_for_new_loop() -> None:
    # 同步测试中串行跑两个事件循环：同一 holder 在第二个循环必须重建 client，
    # 避免复用旧循环上的连接句柄。
    holder = _SharedClientHolder()
    clients: list[httpx.AsyncClient] = []

    async def _use_holder() -> None:
        clients.append(holder.get())

    first_loop = asyncio.new_event_loop()
    try:
        first_loop.run_until_complete(_use_holder())
    finally:
        first_loop.close()

    second_loop = asyncio.new_event_loop()
    try:
        second_loop.run_until_complete(_use_holder())
    finally:
        second_loop.close()

    assert clients[0] is not clients[1]
    asyncio.run(clients[0].aclose())
    asyncio.run(clients[1].aclose())


@pytest.mark.unit
async def test_shared_client_uses_connection_pool_and_http2() -> None:
    client = get_shared_llm_http_client()
    assert client._transport._pool._http2 is True  # type: ignore[attr-defined]
    assert client._transport._pool._max_connections > 0  # type: ignore[attr-defined]
