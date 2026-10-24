"""Investigator side: sign-in, case management, and the reporter <-> investigator channel."""

from datetime import timedelta

import jwt
import pytest
from sqlalchemy import select

from app.core import security
from app.core.config import settings
from app.db.session import open_session
from app.models.beacon import Beacon
from app.models.report import Report
from app.services.gemini import gemini
from app.services.scoring_service import ScoringService
from tests.fake_ai import error_body
from tests.helpers import ADMIN_PASSWORD, API, admin_headers, new_session, run_full_intake, same_pixels, say, script_full_intake

UNKNOWN_CASE = "00000000-0000-4000-8000-000000000000"


async def make_case(client, fake_ai) -> dict:
    """Submit a complete report; returns {'case_id', 'secret_key', 'id' (the admin-side UUID)}."""
    final = await run_full_intake(client, fake_ai, await new_session(client))
    listing = (await client.get(f"{API}/admin/reports/", headers=await admin_headers(client))).json()
    case = next(c for c in listing if c["case_id"] == final["case_id"])
    return {"case_id": final["case_id"], "secret_key": final["secret_key"], "id": case["id"]}


def creds(case: dict) -> dict:
    return {"case_id": case["case_id"], "secret_key": case["secret_key"]}


# ======================================================================================
# Sign-in
# ======================================================================================
async def test_login_works_with_the_configured_password(client):
    response = await client.post(f"{API}/admin/auth/login", json={"username": "BeaconAI", "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["user"] == {"username": "beaconai", "role": "admin"}
    assert jwt.decode(body["access_token"], options={"verify_signature": False})["sub"] == "beaconai"


@pytest.mark.parametrize("password", ["BeaconAI@26", "x", "correct horse battery stapl"])
async def test_the_old_hardcoded_password_no_longer_works(client, password):
    response = await client.post(f"{API}/admin/auth/login", json={"username": "beaconai", "password": password})
    assert response.status_code == 401 and response.json()["code"] == "invalid_credentials"


async def test_login_is_disabled_when_no_password_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", None)
    response = await client.post(f"{API}/admin/auth/login", json={"username": "beaconai", "password": "BeaconAI@26"})
    assert response.status_code == 503 and response.json()["code"] == "admin_login_not_configured"


async def test_repeated_failures_lock_the_client_out(client, enable_rate_limits):
    for _ in range(6):
        assert (await client.post(f"{API}/admin/auth/login", json={"username": "beaconai", "password": "nope"})).status_code == 401
    locked = await client.post(f"{API}/admin/auth/login", json={"username": "beaconai", "password": ADMIN_PASSWORD})
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) > 60, "even the right password is refused while locked"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/admin/reports/"),
        ("get", f"/admin/reports/{UNKNOWN_CASE}"),
        ("get", "/admin/system/status"),
        ("put", f"/admin/reports/{UNKNOWN_CASE}/status"),
        ("post", f"/admin/reports/{UNKNOWN_CASE}/update"),
    ],
)
async def test_admin_endpoints_reject_missing_forged_expired_and_foreign_tokens(client, method, path):
    call = getattr(client, method)
    assert (await call(f"{API}{path}")).status_code == 401
    assert (await call(f"{API}{path}", headers={"Authorization": "Bearer not.a.jwt"})).status_code == 401
    forged = jwt.encode({"sub": "beaconai", "exp": 4102444800}, "attacker-secret-0123456789abcdef0123456789", algorithm="HS256")
    assert (await call(f"{API}{path}", headers={"Authorization": f"Bearer {forged}"})).status_code == 401
    expired = security.create_access_token("beaconai", timedelta(seconds=-1))
    assert (await call(f"{API}{path}", headers={"Authorization": f"Bearer {expired}"})).status_code == 401
    someone_else = security.create_access_token("not-the-admin")
    assert (await call(f"{API}{path}", headers={"Authorization": f"Bearer {someone_else}"})).status_code == 401


# ======================================================================================
# Cases
# ======================================================================================
async def test_listing_detail_and_priority(client, fake_ai):
    case = await make_case(client, fake_ai)
    headers = await admin_headers(client)

    listing = (await client.get(f"{API}/admin/reports/", headers=headers)).json()
    assert listing[0]["case_id"] == case["case_id"] and listing[0]["status"] == "Pending"
    assert listing[0]["credibility_score"] == 43 and listing[0]["priority"] == "Medium" and listing[0]["confidence"] == "Medium"

    detail = (await client.get(f"{API}/admin/reports/{case['id']}", headers=headers)).json()
    assert detail["reporter_details"]["who"] == "Officer Raj" and detail["ai_summary"] == fake_ai.summary
    assert detail["ai_explanation"]["narrative_score"] == 28 and detail["ai_explanation"]["evidence_score"] == 0, (
        "no evidence uploaded -> 0 points"
    )
    assert detail["analysis_status"] == "completed" and detail["updates"] == []
    assert "secret" not in str(detail).lower()

    assert (await client.get(f"{API}/admin/reports/{UNKNOWN_CASE}", headers=headers)).status_code == 404


async def test_status_changes_are_validated_and_visible_to_the_reporter(client, fake_ai):
    case = await make_case(client, fake_ai)
    headers = await admin_headers(client)
    assert (await client.put(f"{API}/admin/reports/{case['id']}/status", json={"status": "Hacked"}, headers=headers)).status_code == 422
    response = await client.put(f"{API}/admin/reports/{case['id']}/status", json={"status": "Ongoing"}, headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "Ongoing"
    assert (await client.post(f"{API}/public/track", json=creds(case))).json()["status"] == "Ongoing"


async def test_background_analysis_does_not_move_the_reporter_visible_timestamp(client, fake_ai):
    case = await make_case(client, fake_ai)
    async with open_session() as db:
        before = (await db.execute(select(Beacon.last_updated_at))).scalar_one()
        report_id = (await db.execute(select(Report.id))).scalar_one()
    await ScoringService.run_background_scoring(str(report_id), case["case_id"])
    async with open_session() as db:
        assert (await db.execute(select(Beacon.last_updated_at))).scalar_one() == before


# ======================================================================================
# Publishing updates
# ======================================================================================
async def test_update_is_rewritten_by_ai_and_published(client, fake_ai):
    case = await make_case(client, fake_ai)
    headers = await admin_headers(client)
    response = await client.post(
        f"{API}/admin/reports/{case['id']}/update",
        json={"raw_update": "Raj suspended pending enquiry, call SP Kumar", "status": "Ongoing"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {**response.json(), "public_update": fake_ai.rewritten, "rewritten": True, "status": "Ongoing"}
    tracked = (await client.post(f"{API}/public/track", json=creds(case))).json()
    assert tracked["updates"][0]["message"] == fake_ai.rewritten
    assert "Kumar" not in str(tracked), "the internal wording is not what the reporter sees"


async def test_update_never_silently_publishes_the_internal_note_when_ai_is_down(client, fake_ai):
    case = await make_case(client, fake_ai)
    headers = await admin_headers(client)
    fake_ai.fail_everything = (503, error_body("UNAVAILABLE", "down", 503))
    url, note = f"{API}/admin/reports/{case['id']}/update", {"raw_update": "Internal: informant is the clerk"}

    failed = await client.post(url, json=note, headers=headers)
    assert failed.status_code == 503 and failed.json()["code"] == "ai_unavailable"
    assert (await client.post(f"{API}/public/track", json=creds(case))).json()["updates"] == [], "nothing was published"

    explicit = await client.post(url, json={**note, "publish_raw": True}, headers=headers)
    assert explicit.status_code == 200 and explicit.json()["rewritten"] is False


# ======================================================================================
# Two-way messages and attachments
# ======================================================================================
async def test_message_roundtrip_with_attachments_and_cross_case_protection(client, fake_ai, png_bytes):
    case_a, case_b = await make_case(client, fake_ai), await make_case(client, fake_ai)
    headers = await admin_headers(client)

    # reporter A uploads a file and sends it
    up = await client.post(f"{API}/public/track/upload", data=creds(case_a), files={"file": ("proof.png", png_bytes, "image/png")})
    assert up.status_code == 200 and up.json()["file_path"].startswith("local://evidence/track/")
    attachment = {k: up.json()[k] for k in ("file_name", "file_path", "mime_type")}
    sent = await client.post(
        f"{API}/public/track/message", json={**creds(case_a), "content": "More proof attached", "attachments": [attachment]}
    )
    assert sent.status_code == 200
    link = sent.json()["attachments"][0]["file_path"]
    assert link.startswith(f"{API}/files?ref="), "the reporter only ever sees a signed link"
    assert same_pixels((await client.get(link)).content, png_bytes)

    # reporter B cannot attach A's file to B's own message, nor smuggle in an arbitrary URL
    forged = await client.post(f"{API}/public/track/message", json={**creds(case_b), "content": "mine now", "attachments": [attachment]})
    assert forged.status_code == 422 and forged.json()["code"] == "invalid_attachment"
    junk = {"file_name": "x", "file_path": "https://evil.example/phish", "mime_type": "image/png"}
    assert (
        await client.post(f"{API}/public/track/message", json={**creds(case_b), "content": "x", "attachments": [junk]})
    ).status_code == 422
    assert (await client.post(f"{API}/public/track/message", json=creds(case_b))).status_code == 422, "empty message"

    # the investigator sees it and replies (the legacy placeholder fields are ignored), and the reporter sees the reply
    inbox = (await client.get(f"{API}/admin/reports/{case_a['id']}/messages", headers=headers)).json()
    assert [m["sender_role"] for m in inbox] == ["user"] and inbox[0]["content"] == "More proof attached"
    reply = await client.post(
        f"{API}/admin/reports/{case_a['id']}/message",
        json={"case_id": "ignored", "secret_key": "ADMIN_BYPASS", "content": "Thanks, we are looking into it", "attachments": []},
        headers=headers,
    )
    assert reply.status_code == 200 and reply.json()["sender_role"] == "admin"
    assert [m["sender_role"] for m in (await client.post(f"{API}/public/track", json=creds(case_a))).json()["messages"]] == [
        "user",
        "admin",
    ]
    assert (await client.post(f"{API}/public/track", json=creds(case_b))).json()["messages"] == [], "B's thread is untouched"

    # admin attachments are bound to the case as well
    admin_up = await client.post(
        f"{API}/admin/reports/{case_a['id']}/upload", files={"file": ("letter.png", png_bytes, "image/png")}, headers=headers
    )
    assert admin_up.status_code == 200
    wrong_case = await client.post(
        f"{API}/admin/reports/{case_b['id']}/message",
        json={"content": "see attached", "attachments": [{k: admin_up.json()[k] for k in ("file_name", "file_path", "mime_type")}]},
        headers=headers,
    )
    assert wrong_case.status_code == 422


# ======================================================================================
# Operations
# ======================================================================================
async def test_failed_analysis_can_be_requeued_by_the_admin(client, fake_ai):
    session = await new_session(client)
    messages = script_full_intake(fake_ai)
    for message in messages[:-1]:
        await say(client, session, message)

    # chat works, but the AI is down for the background analysis that follows submission
    fake_ai.fail_tasks = {
        "summary": (503, error_body("UNAVAILABLE", "down", 503)),
        "scoring": (503, error_body("UNAVAILABLE", "down", 503)),
    }
    final = (await say(client, session, messages[-1])).json()
    headers = await admin_headers(client)
    case = (await client.get(f"{API}/admin/reports/", headers=headers)).json()[0]
    assert case["case_id"] == final["case_id"] and case["analysis_status"] == "failed"
    assert case["credibility_score"] is None and case["priority"] == "Pending"

    # AI recovers; the admin presses "Recalculate"
    fake_ai.fail_tasks = {}
    for model in ("m-a", "m-b"):
        gemini.registry.health(model).state = "closed"
    assert (await client.post(f"{API}/admin/reports/{case['id']}/analyze", headers=headers)).status_code == 202
    after = (await client.get(f"{API}/admin/reports/{case['id']}", headers=headers)).json()
    assert after["analysis_status"] == "completed" and after["credibility_score"] == 43


async def test_system_status_for_admins(client, fake_ai):
    status = (await client.get(f"{API}/admin/system/status", headers=await admin_headers(client))).json()
    assert status["storage"] == "local" and status["ai"]["state"] in {"ok", "unknown"}
    assert {row["model"] for row in status["ai"]["quality_chain"]} == {"m-a", "m-b"}
    assert "test-gemini-key" not in str(status), "secrets never appear in status output"
