"""LLM 出站调用的共享 httpx.AsyncClient。

每次 LLM 调用新建 client 都会重复 TCP + TLS 握手（0.3~2s），会话高峰期
（如 4 路子 Agent 并发）尤为明显。这里按事件循环缓存一个共享 client：
启用 HTTP/2 与 keep-alive 连接池，对 deepseek 等单域名高并发收益明显。

按事件循环缓存而非纯模块级单例，是因为 pytest-asyncio 等「一用例一事件
循环」场景下，旧循环的连接句柄不能被新循环复用。
"""

from __future__ import annotations

import asyncio

import httpx

from cygnusx.core.config import get_settings


class _SharedClientHolder:
    """每个事件循环持有一个共享 client；切换循环时惰性重建。"""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def get(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._client is None or self._loop is not loop:
            settings = get_settings()
            self._client = httpx.AsyncClient(
                verify=True,
                follow_redirects=True,
                http2=True,
                limits=httpx.Limits(
                    max_connections=settings.llm_http_max_connections,
                    max_keepalive_connections=settings.llm_http_max_keepalive_connections,
                    keepalive_expiry=30.0,
                ),
            )
            self._loop = loop
        return self._client


_shared_holder = _SharedClientHolder()


def get_shared_llm_http_client() -> httpx.AsyncClient:
    """获取当前事件循环的共享 LLM 出站 client（连接池 + HTTP/2）。"""
    return _shared_holder.get()
