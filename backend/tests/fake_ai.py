"""A scriptable stand-in for the Gemini API, plugged in underneath the real client (HTTP level), so the whole
stack - fallback chain, parsing, chat agent, scoring - runs for real in tests."""

import json
from collections.abc import Callable
from typing import Any

import httpx

from app.services.gemini import gemini
from app.services.gemini.registry import ModelRegistry
from tests.gemini_helpers import error_body, ok_body, respond

CHAT_DEFAULT = {"reply": "I understand. Could you tell me more?", "extracted": {}, "asked_about": "none", "ready_to_submit": False}


def turn(reply: str, *, asked: str = "none", ready: bool = False, **facts: str) -> dict[str, Any]:
    return {"reply": reply, "extracted": facts, "asked_about": asked, "ready_to_submit": ready}


class FakeAI:
    def __init__(self) -> None:
        self.chat_script: list[dict[str, Any] | Callable[[dict[str, Any]], dict[str, Any]]] = []
        self.calls: list[dict[str, Any]] = []
        self.fail_models: dict[str, tuple[int, dict[str, Any]]] = {}  # model -> (status, body)
        self.fail_tasks: dict[str, tuple[int, dict[str, Any]]] = {}  # task name -> (status, body)
        self.fail_everything: tuple[int, dict[str, Any]] | None = None
        self.block_chat = False
        self.score = {
            "narrative_credibility": {"score": 28, "reasoning": ["Specific names, place and time were given."]},
            "evidence_strength": {"score": 22, "reasoning": ["Photo is consistent with the claim."]},
            "behavioral_reliability": {"score": 15, "reasoning": ["Cooperative."]},
            "rationale": ["Detailed account with a matching photo."],
            "limitations": ["Nothing could be independently verified."],
        }
        self.summary = "A citizen reports that an officer demanded a bribe at the checkpoint."
        self.image = {"description": "A uniformed officer next to a vehicle.", "visible_text": "CHECK POST 4", "legible": True}
        self.transcript = "Give me five hundred rupees."
        self.rewritten = "The matter has been assigned to an investigator."

    # ---- request classification -----------------------------------------------------
    @staticmethod
    def task_of(payload: dict[str, Any]) -> str:
        system = (payload.get("systemInstruction") or {}).get("parts", [{}])[0].get("text", "")
        if "You are Beacon AI" in system:
            return "chat"
        if "Credibility Engine" in system:
            return "scoring"
        if "case summaries" in system:
            return "summary"
        if "analyse photos and scans" in system:
            return "vision"
        if "Rewrite the internal case update" in system:
            return "rewrite"
        return "transcribe"

    # ---- the transport ----------------------------------------------------------------
    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":  # model discovery
            return respond(200, {"models": []})
        model = request.url.path.split("/models/")[-1].split(":")[0]
        payload = json.loads(request.content)
        task = self.task_of(payload)
        self.calls.append({"model": model, "task": task, "payload": payload})

        if self.fail_everything:
            return respond(*self.fail_everything)
        if model in self.fail_models:
            return respond(*self.fail_models[model])
        if task in self.fail_tasks:
            return respond(*self.fail_tasks[task])

        if task == "chat":
            if self.block_chat:
                return respond(200, {"promptFeedback": {"blockReason": "SAFETY"}})
            step = self.chat_script.pop(0) if self.chat_script else dict(CHAT_DEFAULT)
            if callable(step):
                step = step(payload)
            return respond(200, ok_body(json.dumps(step)))
        if task == "scoring":
            return respond(200, ok_body(json.dumps(self.score)))
        if task == "summary":
            return respond(200, ok_body(self.summary))
        if task == "vision":
            return respond(200, ok_body(json.dumps(self.image)))
        if task == "rewrite":
            return respond(200, ok_body(self.rewritten))
        return respond(200, ok_body(self.transcript))

    # ---- helpers ------------------------------------------------------------------------
    def tasks(self) -> list[str]:
        return [c["task"] for c in self.calls]

    def install(self) -> None:
        """Re-initialise the application's shared Gemini client to talk to this fake."""

        async def no_sleep(_s: float) -> None:
            return None

        gemini.__init__(  # type: ignore[misc]
            registry=ModelRegistry(quality=("m-a", "m-b"), fast=("m-a", "m-b")),
            transport=httpx.MockTransport(self),
            sleep=no_sleep,
        )


__all__ = ["FakeAI", "error_body", "turn"]
