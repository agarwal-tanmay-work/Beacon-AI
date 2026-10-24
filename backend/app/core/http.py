"""A lazily created ``httpx.AsyncClient`` that is bound to the *running* event loop.

An ``AsyncClient`` must only be used on the loop it was created on. The old code shared one class-level
client between the main loop and a second loop it spun up inside a worker thread, which is a classic
source of "Event loop is closed" / "attached to a different loop" errors that surface as random AI failures.
"""

import asyncio
from typing import Any

import httpx


class SharedHttpClient:
    def __init__(self, **client_kwargs: Any) -> None:
        self._kwargs = client_kwargs
        self._client: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def get(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._client is None or self._client.is_closed or self._loop is not loop:
            self._client = httpx.AsyncClient(**self._kwargs)
            self._loop = loop
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            try:
                await self._client.aclose()
            except RuntimeError:  # closed from a different loop (tests): nothing useful left to do
                pass
        self._client = None
