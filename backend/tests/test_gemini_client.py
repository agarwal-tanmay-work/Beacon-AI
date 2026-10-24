"""The fallback chain is the heart of the 'Gemini 2.5 Flash is gone' fix - test every failure class."""

import asyncio

import pytest
from pydantic import BaseModel

from app.services.gemini.client import GenerationRequest, build_payload, classify_http_error, extract_text
from app.services.gemini.errors import (
    GeminiAuthError,
    GeminiBadRequest,
    GeminiBlocked,
    GeminiEmptyResponse,
    GeminiModelUnavailable,
    GeminiNotConfigured,
    GeminiOverloaded,
    GeminiQuotaExceeded,
    GeminiRateLimited,
    GeminiTimeout,
    GeminiUnavailable,
)
from app.services.gemini.registry import ModelRegistry, default_caps
from app.services.gemini.schema import extract_json, make_parser, schema_for
from tests.gemini_helpers import Recorder, error_body, make_client, ok_body, respond

REQ = GenerationRequest(contents=[{"role": "user", "parts": [{"text": "hi"}]}], label="test")


def lazy(status, body=None, headers=None):
    return lambda: respond(status, body, headers)


# ======================================================================================
# classify_http_error
# ======================================================================================
@pytest.mark.parametrize(
    ("status", "api_status", "message", "expected"),
    [
        (404, "NOT_FOUND", "models/gemini-2.5-flash is not found for API version v1beta", GeminiModelUnavailable),
        (403, "PERMISSION_DENIED", "You do not have access to this model", GeminiModelUnavailable),
        (403, "PERMISSION_DENIED", "Your API key was reported as leaked. Please use another API key.", GeminiAuthError),
        (400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.", GeminiAuthError),
        (401, "UNAUTHENTICATED", "Request had invalid authentication credentials", GeminiAuthError),
        (403, "PERMISSION_DENIED", "Generative Language API has not been used in project 123 before or it is disabled", GeminiAuthError),
        (400, "FAILED_PRECONDITION", "User location is not supported for the API use.", GeminiAuthError),
        (503, "UNAVAILABLE", "The model is overloaded. Please try again later.", GeminiOverloaded),
        (500, "INTERNAL", "Internal error encountered.", GeminiOverloaded),
        (504, "DEADLINE_EXCEEDED", "Deadline expired", GeminiTimeout),
        (429, "RESOURCE_EXHAUSTED", "Quota exceeded for metric ..., limit: 0, model: gemini-2.5-flash", GeminiQuotaExceeded),
    ],
)
def test_classification(status, api_status, message, expected):
    assert isinstance(classify_http_error(status, error_body(api_status, message, status)), expected)


def test_429_per_minute_is_rate_limit_with_retry_delay():
    body = error_body(
        "RESOURCE_EXHAUSTED",
        "You exceeded your current quota. Please retry in 35.5s.",
        429,
        details=[
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}],
            },
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "35s"},
        ],
    )
    error = classify_http_error(429, body)
    assert isinstance(error, GeminiRateLimited)
    assert error.retry_after == 35


def test_429_per_day_is_quota_exceeded():
    body = error_body(
        "RESOURCE_EXHAUSTED",
        "You exceeded your current quota.",
        429,
        details=[
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
            }
        ],
    )
    assert isinstance(classify_http_error(429, body), GeminiQuotaExceeded)


def test_400_thinking_and_schema_hints():
    thinking = classify_http_error(400, error_body("INVALID_ARGUMENT", "thinking_level is not supported by this model", 400))
    assert isinstance(thinking, GeminiBadRequest) and thinking.adaptation == "thinking"
    schema = classify_http_error(400, error_body("INVALID_ARGUMENT", 'Unknown name "responseJsonSchema": Cannot find field.', 400))
    assert isinstance(schema, GeminiBadRequest) and schema.adaptation == "schema"


def test_new_style_string_error_codes():
    assert isinstance(classify_http_error(404, {"error": {"code": "model_not_found", "message": "x"}}), GeminiModelUnavailable)
    assert isinstance(classify_http_error(429, {"error": {"code": "quota_exceeded", "message": "x"}}), GeminiQuotaExceeded)


def test_unparseable_error_body():
    assert isinstance(classify_http_error(502, None), GeminiOverloaded)
    assert isinstance(classify_http_error(418, "teapot"), GeminiBadRequest)


# ======================================================================================
# extract_text
# ======================================================================================
def test_extract_text_joins_parts_and_skips_thoughts():
    data = {
        "candidates": [
            {"content": {"parts": [{"text": "hidden", "thought": True}, {"text": "Hello "}, {"text": "world"}]}, "finishReason": "STOP"}
        ]
    }
    assert extract_text(data)[0] == "Hello world"


def test_extract_text_handles_missing_parts_as_empty_not_keyerror():
    with pytest.raises(GeminiEmptyResponse) as exc:
        extract_text({"candidates": [{"content": {"role": "model"}, "finishReason": "MAX_TOKENS"}]})
    assert exc.value.truncated is True  # thinking ate the whole token budget


@pytest.mark.parametrize("data", [{}, {"candidates": []}, {"candidates": [{"content": {"parts": [{"text": "   "}]}}]}])
def test_extract_text_empty_variants(data):
    with pytest.raises(GeminiEmptyResponse):
        extract_text(data)


def test_extract_text_blocks():
    with pytest.raises(GeminiBlocked):
        extract_text({"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(GeminiBlocked):
        extract_text({"candidates": [{"finishReason": "PROHIBITED_CONTENT"}]})


# ======================================================================================
# Payload construction
# ======================================================================================
def test_payload_never_sets_sampling_parameters():
    registry = ModelRegistry()
    payload = build_payload(REQ, "gemini-3.8-flash", registry)
    config = payload["generationConfig"]
    assert not {"temperature", "topP", "topK"} & set(config)  # ignored on 3.6+, a 400 soon
    assert config["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert config["maxOutputTokens"] == 4096


def test_payload_schema_and_system_instruction():
    registry = ModelRegistry()
    request = GenerationRequest(contents=[], system_instruction="be kind", response_schema={"type": "object"})
    payload = build_payload(request, "gemini-3.8-flash", registry)
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["generationConfig"]["responseJsonSchema"] == {"type": "object"}
    assert payload["systemInstruction"]["parts"][0]["text"] == "be kind"


def test_legacy_25_models_use_thinking_budget_not_level():
    registry = ModelRegistry()
    assert default_caps("gemini-2.5-flash").thinking_style == "budget"
    config = build_payload(REQ, "gemini-2.5-flash", registry)["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingBudget": 0}


# ======================================================================================
# Fallback chain behaviour
# ======================================================================================
async def test_happy_path_uses_header_auth_and_no_key_in_url():
    recorder = Recorder({"m-a": [lazy(200, ok_body("pong"))]})
    client, _ = make_client(recorder)
    value, result = await client.generate(REQ)
    assert value == "pong" and result.model == "m-a"
    call = recorder.requests[0]
    assert call["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert "test-gemini-key" not in call["url"] and "key=" not in call["url"]
    await client.aclose()


async def test_retired_model_falls_back_and_is_not_retried():
    """The reported bug: gemini-2.5-flash stops being served -> chat must still work."""
    recorder = Recorder(
        {
            "m-a": [lazy(404, error_body("NOT_FOUND", "models/m-a is not found", 404))],
            "m-b": [lazy(200, ok_body("from b"))],
        }
    )
    client, _ = make_client(recorder)
    first, result = await client.generate(REQ)
    assert (first, result.model) == ("from b", "m-b")
    assert recorder.models_called == ["m-a", "m-b"]

    await client.generate(REQ)  # m-a is paused by its breaker now: no second round trip
    assert recorder.models_called == ["m-a", "m-b", "m-b"]
    await client.aclose()


async def test_daily_quota_moves_on_and_pauses_model():
    quota = error_body(
        "RESOURCE_EXHAUSTED",
        "quota",
        429,
        details=[
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
            }
        ],
    )
    recorder = Recorder({"m-a": [lazy(429, quota)], "m-b": [lazy(200, ok_body("ok"))]})
    client, clock = make_client(recorder)
    await client.generate(REQ)
    assert client.registry.health("m-a").state == "open"
    # an hour later the model gets probed again
    clock.advance(3601)
    recorder.script["m-a"] = [lazy(200, ok_body("a again"))]
    value, result = await client.generate(REQ)
    assert (value, result.model) == ("a again", "m-a")
    assert client.registry.health("m-a").state == "closed"
    await client.aclose()


async def test_transient_503_gets_one_retry_on_same_model_then_succeeds():
    recorder = Recorder({"m-a": [lazy(503, error_body("UNAVAILABLE", "overloaded", 503)), lazy(200, ok_body("recovered"))]})
    client, _ = make_client(recorder)
    value, result = await client.generate(REQ)
    assert (value, result.model) == ("recovered", "m-a")
    assert recorder.models_called == ["m-a", "m-a"]
    await client.aclose()


async def test_persistent_503_falls_through_to_next_model():
    recorder = Recorder({"m-a": [lazy(503, error_body("UNAVAILABLE", "overloaded", 503))], "m-b": [lazy(200, ok_body("b"))]})
    client, _ = make_client(recorder)
    value, result = await client.generate(REQ)
    assert result.model == "m-b"
    assert recorder.models_called == ["m-a", "m-a", "m-b"]
    await client.aclose()


async def test_auth_error_stops_chain_and_fails_fast_afterwards():
    recorder = Recorder({"m-a": [lazy(400, error_body("INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.", 400))]})
    client, clock = make_client(recorder)
    with pytest.raises(GeminiAuthError):
        await client.generate(REQ)
    assert recorder.models_called == ["m-a"]  # did not waste calls on m-b / m-c
    assert client.health() == "key_invalid"
    with pytest.raises(GeminiAuthError):
        await client.generate(REQ)  # paused: no HTTP request at all
    assert len(recorder.requests) == 1
    await client.aclose()


async def test_leaked_key_message_is_surfaced():
    recorder = Recorder(
        {"m-a": [lazy(403, error_body("PERMISSION_DENIED", "Your API key was reported as leaked. Please use another API key.", 403))]}
    )
    client, _ = make_client(recorder)
    with pytest.raises(GeminiAuthError, match="leaked"):
        await client.generate(REQ)
    assert "leaked" in (client.status()["key_error"] or "")
    await client.aclose()


async def test_thinking_exhausting_token_budget_retries_with_bigger_budget():
    def script(model, payload, index):
        if payload["generationConfig"]["maxOutputTokens"] < 8000:
            return respond(200, {"candidates": [{"content": {"role": "model"}, "finishReason": "MAX_TOKENS"}]})
        return respond(200, ok_body("finally"))

    recorder = Recorder(script)
    client, _ = make_client(recorder)
    request = GenerationRequest(contents=[], max_output_tokens=4096)
    value, _ = await client.generate(request)
    assert value == "finally"
    assert [r["payload"]["generationConfig"]["maxOutputTokens"] for r in recorder.requests] == [4096, 8192]
    await client.aclose()


class Tiny(BaseModel):
    reply: str


async def test_unparseable_json_is_a_failed_attempt_so_next_model_runs():
    recorder = Recorder({"m-a": [lazy(200, ok_body("not json at all"))], "m-b": [lazy(200, ok_body('{"reply": "hello"}'))]})
    client, _ = make_client(recorder)
    value, result = await client.generate(REQ, parser=make_parser(Tiny))
    assert value.reply == "hello" and result.model == "m-b"
    await client.aclose()


async def test_schema_mismatch_is_malformed_too():
    recorder = Recorder({"m-a": [lazy(200, ok_body('{"wrong": 1}'))], "m-b": [lazy(200, ok_body('{"reply": "ok"}'))]})
    client, _ = make_client(recorder)
    value, _ = await client.generate(REQ, parser=make_parser(Tiny))
    assert value.reply == "ok"
    await client.aclose()


async def test_thinking_400_degrades_request_on_same_model():
    def script(model, payload, index):
        if "thinkingConfig" in payload["generationConfig"]:
            return respond(400, error_body("INVALID_ARGUMENT", "Thinking level is not supported for this model", 400))
        return respond(200, ok_body("worked without thinking"))

    recorder = Recorder(script)
    client, _ = make_client(recorder)
    value, result = await client.generate(REQ)
    assert value == "worked without thinking" and result.model == "m-a"
    # 'LOW' -> 'low' -> none: two adaptations, then success, all on the first model
    assert recorder.models_called == ["m-a", "m-a", "m-a"]
    assert client.registry.caps("m-a").thinking_style == "none"
    await client.aclose()


async def test_schema_400_degrades_to_prompt_only_json():
    def script(model, payload, index):
        cfg = payload["generationConfig"]
        if "responseJsonSchema" in cfg or "responseFormat" in cfg:
            return respond(400, error_body("INVALID_ARGUMENT", 'Invalid JSON payload: Unknown name "responseJsonSchema"', 400))
        return respond(200, ok_body('{"reply": "ok"}'))

    recorder = Recorder(script)
    client, _ = make_client(recorder)
    request = GenerationRequest(contents=[], response_schema=schema_for(Tiny))
    value, _ = await client.generate(request, parser=make_parser(Tiny))
    assert value.reply == "ok"
    last = recorder.requests[-1]["payload"]
    assert "JSON Schema" in last["systemInstruction"]["parts"][0]["text"]
    await client.aclose()


async def test_timeout_moves_to_next_model_without_retrying_the_slow_one():
    import httpx

    def script(model, payload, index):
        if model == "m-a":
            raise httpx.ReadTimeout("slow")
        return respond(200, ok_body("fast"))

    recorder = Recorder(script)
    client, _ = make_client(recorder)
    value, result = await client.generate(REQ)
    assert result.model == "m-b" and recorder.models_called == ["m-a", "m-b"]
    await client.aclose()


async def test_content_blocked_by_two_models_raises_blocked():
    blocked = lazy(200, {"promptFeedback": {"blockReason": "SAFETY"}})
    recorder = Recorder({"m-a": [blocked], "m-b": [blocked], "m-c": [blocked]})
    client, _ = make_client(recorder)
    with pytest.raises(GeminiBlocked):
        await client.generate(REQ)
    assert len(recorder.requests) == 2  # stops shopping around after two refusals
    await client.aclose()


async def test_all_models_failing_raises_unavailable_with_report():
    recorder = Recorder({m: [lazy(503, error_body("UNAVAILABLE", "down", 503))] for m in ("m-a", "m-b", "m-c")})
    client, _ = make_client(recorder)
    with pytest.raises(GeminiUnavailable) as exc:
        await client.generate(REQ)
    assert {a.model for a in exc.value.attempts} == {"m-a", "m-b", "m-c"}
    await client.aclose()


async def test_everything_paused_for_hours_fails_fast_without_http_calls():
    gone = lazy(404, error_body("NOT_FOUND", "gone", 404))
    recorder = Recorder({m: [gone] for m in ("m-a", "m-b", "m-c")})
    client, _ = make_client(recorder)
    with pytest.raises(GeminiUnavailable):
        await client.generate(REQ)
    calls = len(recorder.requests)
    with pytest.raises(GeminiUnavailable):
        await client.generate(REQ)
    assert len(recorder.requests) == calls  # all three are paused for 30+ min: no blind retries
    assert client.health() == "degraded"
    await client.aclose()


async def test_short_pause_is_probed_instead_of_failing_the_user():
    """All models paused only briefly (e.g. a rate limit burst): probe the soonest one right away."""
    rate = error_body(
        "RESOURCE_EXHAUSTED",
        "slow down. Please retry in 5s",
        429,
        details=[{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "5s"}],
    )
    recorder = Recorder({"m-a": [lazy(429, rate), lazy(200, ok_body("back"))], "m-b": [lazy(429, rate)], "m-c": [lazy(429, rate)]})
    client, _ = make_client(recorder)
    with pytest.raises(GeminiUnavailable):
        await client.generate(REQ)
    value, _ = await client.generate(REQ)  # every model is paused ~5-15s, but the pause is short -> forced probe
    assert value == "back"
    await client.aclose()


async def test_missing_api_key_raises_not_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    client, _ = make_client(Recorder({}))
    with pytest.raises(GeminiNotConfigured):
        await client.generate(REQ)
    assert client.health() == "unconfigured"
    await client.aclose()


async def test_concurrent_requests_share_a_single_probe_of_a_recovering_model():
    gone = lazy(404, error_body("NOT_FOUND", "gone", 404))
    recorder = Recorder({"m-a": [gone], "m-b": [lazy(200, ok_body("b"))]})
    client, clock = make_client(recorder)
    await client.generate(REQ)
    clock.advance(31 * 60)
    recorder.script["m-a"] = [lazy(200, ok_body("a"))]
    results = await asyncio.gather(*(client.generate(REQ) for _ in range(5)))
    assert sum(1 for _, r in results if r.model == "m-a") >= 1
    await client.aclose()


# ======================================================================================
# Discovery + registry
# ======================================================================================
def test_discovery_never_reorders_the_configured_chain():
    registry = ModelRegistry(quality=("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"))
    registry.apply_discovery(
        [
            {"name": "models/gemini-3.9-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
        ]
    )
    assert registry.chain("quality") == ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"]


def test_default_chains_follow_the_requested_order():
    registry = ModelRegistry()
    assert registry.chain("quality") == [
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-flash-lite-latest",
    ]
    assert registry.chain("fast") == [
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash",
        "gemini-flash-latest",
    ]


def test_discovery_ignores_empty_listing():
    registry = ModelRegistry(quality=("a", "b"))
    registry.apply_discovery([])
    assert registry.chain("quality") == ["a", "b"]


def test_discovery_disables_thinking_config_for_non_thinking_models():
    registry = ModelRegistry(quality=("gemini-3.8-flash",))
    registry.apply_discovery([{"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"], "thinking": False}])
    assert "thinkingConfig" not in build_payload(REQ, "gemini-3.8-flash", registry)["generationConfig"]


# ======================================================================================
# Schema + JSON helpers
# ======================================================================================
def test_schema_for_strips_unsupported_keys_and_marks_all_required():
    class Inner(BaseModel):
        note: str = "x"

    class Outer(BaseModel):
        name: str
        score: int = 3
        inner: Inner

    schema = schema_for(Outer)
    assert schema["required"] == ["name", "score", "inner"]
    assert "default" not in str(schema) and "title" not in str(schema)
    assert schema["$defs"]["Inner"]["required"] == ["note"]


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here you go: {"a": {"b": "}"}} hope that helps') == {"a": {"b": "}"}}
    with pytest.raises(Exception):
        extract_json("no json here")
