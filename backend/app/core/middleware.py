"""Pure-ASGI middlewares: request body limit and security headers."""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Reject over-sized request bodies *while they stream in*.

    Starlette's multipart parser happily spools a multi-gigabyte upload to disk before any endpoint code runs, so
    the limit has to be enforced at the ASGI level: by the declared Content-Length when there is one, and by
    counting bytes when there is not (chunked uploads).
    """

    def __init__(self, app: ASGIApp, *, default_limit: int, upload_limit: int, upload_suffixes: tuple[str, ...] = ("/upload",)) -> None:
        self.app = app
        self.default_limit = default_limit
        self.upload_limit = upload_limit
        self.upload_suffixes = upload_suffixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return

        limit = self.upload_limit if scope["path"].endswith(self.upload_suffixes) else self.default_limit
        declared = dict(scope["headers"]).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await self._reject(send, limit)
            return

        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await self._reject(send, limit)

    @staticmethod
    async def _reject(send: Send, limit: int) -> None:
        body = json.dumps({"detail": "The request is too large.", "code": "payload_too_large", "max_bytes": limit}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})


_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
]


class SecurityHeadersMiddleware:
    """Defensive headers on every response. API responses are never cacheable (they carry case data)."""

    def __init__(self, app: ASGIApp, *, docs_prefixes: tuple[str, ...] = ()) -> None:
        self.app = app
        self.docs_prefixes = docs_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        is_docs = path.startswith(self.docs_prefixes) if self.docs_prefixes else False

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend((n, v) for n, v in _SECURITY_HEADERS if n not in present)
                if not is_docs and b"content-security-policy" not in present:
                    headers.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; sandbox"))
                if b"cache-control" not in present and not is_docs:
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


__all__ = ["BodySizeLimitMiddleware", "SecurityHeadersMiddleware"]
