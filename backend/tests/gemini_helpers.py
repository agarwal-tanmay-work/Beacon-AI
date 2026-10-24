"""Test doubles for the Gemini client: a scripted HTTP transport and a controllable clock."""

import json
from collections.abc import Callable
from typing import Any

import httpx

from app.services.gemini.client import GeminiClient
from app.services.gemini.registry import ModelRegistry


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def ok_body(text: str, *, finish: str = "STOP", thought_tokens: int = 10) -> dict[str, Any]:
    return {
        "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": finish}],
        "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 8, "thoughtsTokenCount": thought_tokens},
    }


def error_body(status: str, message: str, code: int, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message, "status": status}}
    if details:
        body["error"]["details"] = details
    return body


def respond(status: int, body: Any = None, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, json=body, headers=headers)


class Recorder:
    """Scripted responses per model + a log of every request the client made."""

    def __init__(self, script: dict[str, list[Any]] | Callable[[str, dict[str, Any], int], httpx.Response]):
        self.script = script
        self.requests: list[dict[str, Any]] = []
        self._counts: dict[str, int] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        model = path.split("/models/")[-1].split(":")[0] if "/models/" in path else path
        payload = json.loads(request.content) if request.content else {}
        self.requests.append({"model": model, "payload": payload, "headers": dict(request.headers), "url": str(request.url)})
        index = self._counts.get(model, 0)
        self._counts[model] = index + 1
        if callable(self.script):
            return self.script(model, payload, index)
        steps = self.script.get(model, [])
        step = steps[min(index, len(steps) - 1)] if steps else respond(404, error_body("NOT_FOUND", "model not found", 404))
        return step() if callable(step) else step

    @property
    def models_called(self) -> list[str]:
        return [r["model"] for r in self.requests]


def make_client(
    recorder: Recorder, *, models: tuple[str, ...] = ("m-a", "m-b", "m-c"), clock: FakeClock | None = None
) -> tuple[GeminiClient, FakeClock]:
    clock = clock or FakeClock()

    async def no_sleep(_seconds: float) -> None:
        return None

    registry = ModelRegistry(quality=models, fast=models, clock=clock)
    client = GeminiClient(registry=registry, transport=httpx.MockTransport(recorder), sleep=no_sleep, clock=clock)
    return client, clock
