"""Credibility scoring rules, the background analysis pipeline, and the self-healing maintenance jobs."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.core import security
from app.core.config import settings
from app.core.time_utils import utc_now
from app.db.session import open_session
from app.models.beacon import Beacon
from app.models.report import Report, ReportStateTracking
from app.schemas.ai import EvidenceDigest, ScoringResult
from app.services import maintenance
from app.services.gemini import gemini
from app.services.scoring_rules import confidence_band, finalize_score, priority_for
from tests.fake_ai import error_body
from tests.helpers import API, new_session, run_full_intake, upload
from tests.test_admin_api import make_case

LEGACY_PBKDF2 = "$pbkdf2-sha256$29000$8p4zxlir9Z4TwjindA7h/A$n0ILWLr4sl72ZViGTfQFvCgY/Z9YVykHHrM8lyU0eLk"  # 'A1B2-C3D4'


def result(narrative: int, evidence: int, behavioral: int) -> ScoringResult:
    sub = lambda score: {"score": score, "reasoning": ["r"]}  # noqa: E731
    return ScoringResult.model_validate(
        {
            "narrative_credibility": sub(narrative),
            "evidence_strength": sub(evidence),
            "behavioral_reliability": sub(behavioral),
            "rationale": ["because"],
            "limitations": [],
        }
    )


GOOD_EVIDENCE = [EvidenceDigest(file_name="a.png", kind="image", description="officer taking cash", analysis_available=True)]


# ======================================================================================
# Deterministic rules
# ======================================================================================
@pytest.mark.parametrize(("score", "band"), [(1, "Low"), (33, "Low"), (34, "Medium"), (66, "Medium"), (67, "High"), (100, "High")])
def test_confidence_bands_match_the_documented_ranges(score, band):
    assert confidence_band(score) == band and priority_for(score) == band
    assert priority_for(None) == "Pending"


def test_total_is_the_sum_of_the_parts_and_parts_are_clamped():
    final = finalize_score(result(28, 22, 15), GOOD_EVIDENCE)
    assert (final.total, final.confidence) == (65, "Medium")
    wild = finalize_score(result(99, 99, 99), GOOD_EVIDENCE)  # a model ignoring the maxima cannot exceed 40 + 40 + 20
    assert (wild.narrative, wild.evidence, wild.behavioral, wild.total, wild.confidence) == (40, 40, 20, 100, "High")


def test_no_usable_evidence_means_zero_evidence_points():
    final = finalize_score(result(30, 25, 10), [])
    assert final.evidence == 0 and final.total == 40
    assert any("No usable supporting evidence" in item for item in final.limitations)
    corrupt = [EvidenceDigest(file_name="x", status="corrupt", analysis_available=True, description="d")]
    duplicate = [EvidenceDigest(file_name="x", status="duplicate", analysis_available=True, description="d")]
    unanalysed = [EvidenceDigest(file_name="x", analysis_available=False)]
    for digests in (corrupt, duplicate, unanalysed):
        assert finalize_score(result(10, 20, 5), digests).evidence == 0


def test_score_is_never_zero_because_the_database_forbids_it():
    assert finalize_score(result(0, 0, 0), []).total == 1


# ======================================================================================
# Pipeline
# ======================================================================================
async def test_analysis_runs_in_order_and_stores_everything(client, fake_ai, png_bytes):
    session = await new_session(client)
    await upload(client, session, png_bytes, name="proof.png")
    await upload(client, session, png_bytes, name="proof-copy.png")  # same bytes -> duplicate
    final = await run_full_intake(client, fake_ai, session)

    order = fake_ai.tasks()
    assert order.index("vision") < order.index("summary") < order.index("scoring")
    scoring_prompt = [c for c in fake_ai.calls if c["task"] == "scoring"][-1]["payload"]["contents"][0]["parts"][0]["text"]
    assert "[VALID]" in scoring_prompt and "[DUPLICATE]" in scoring_prompt and "CHECK POST 4" in scoring_prompt
    assert "Thank you for your courage" not in scoring_prompt, "the submission message is not part of the narrative"

    async with open_session() as db:
        beacon = (await db.execute(select(Beacon).where(Beacon.case_id == final["case_id"]))).scalar_one()
        assert beacon.analysis_status == "completed" and beacon.analysis_attempts == 1 and beacon.credibility_score == 65
        assert beacon.ai_summary == fake_ai.summary and "Medium confidence" in beacon.score_explanation
        assert beacon.ai_explanation["safety"] and beacon.ai_explanation["behavioral_score"] == 15
        assert [e["analyzed"] for e in beacon.evidence_files] == [True, True]
        assert beacon.analysis_last_error is None


async def test_image_analysis_is_cached_not_repeated(client, fake_ai, png_bytes):
    session = await new_session(client)
    await upload(client, session, png_bytes)
    await run_full_intake(client, fake_ai, session)
    vision_calls = fake_ai.tasks().count("vision")
    assert vision_calls == 1, "one vision call at chat time, reused by the scorer (the old code made 2-3 per image)"


async def test_summary_survives_a_scoring_failure_and_is_not_regenerated(client, fake_ai):
    fake_ai.fail_tasks = {"scoring": (503, error_body("UNAVAILABLE", "down", 503))}
    case = await make_case(client, fake_ai)
    async with open_session() as db:
        beacon = (await db.execute(select(Beacon))).scalar_one()
        assert beacon.analysis_status == "failed" and beacon.ai_summary == fake_ai.summary
        assert "overloaded" in beacon.analysis_last_error or "unavailable" in beacon.analysis_last_error
        report_id = (await db.execute(select(Report.id))).scalar_one()

    summaries_before = fake_ai.tasks().count("summary")
    fake_ai.fail_tasks = {}
    for model in ("m-a", "m-b"):
        gemini.registry.health(model).state = "closed"
    from app.services.scoring_service import ScoringService

    await ScoringService.run_background_scoring(str(report_id), case["case_id"])
    assert fake_ai.tasks().count("summary") == summaries_before, "the finished summary is reused"
    async with open_session() as db:
        beacon = (await db.execute(select(Beacon))).scalar_one()
        assert beacon.analysis_status == "completed" and beacon.analysis_attempts == 2


async def test_analysis_never_runs_twice_at_once(client, fake_ai):
    from app.services import scoring_service

    case = await make_case(client, fake_ai)
    async with open_session() as db:
        report_id = (await db.execute(select(Report.id))).scalar_one()
    calls_before = len(fake_ai.calls)
    scoring_service._in_flight.add(case["case_id"])  # noqa: SLF001
    try:
        await scoring_service.ScoringService.run_background_scoring(str(report_id), case["case_id"])
    finally:
        scoring_service._in_flight.discard(case["case_id"])  # noqa: SLF001
    assert len(fake_ai.calls) == calls_before


# ======================================================================================
# Maintenance: recovery of stalled analyses
# ======================================================================================
async def force_state(case_id: str, status: str, attempts: int, age: timedelta) -> None:
    async with open_session() as db:
        await db.execute(
            update(Beacon)
            .where(Beacon.case_id == case_id)
            .values(analysis_status=status, analysis_attempts=attempts, updated_at=utc_now() - age, credibility_score=None, ai_summary=None)
        )
        await db.commit()


@pytest.mark.parametrize(
    ("status", "attempts", "age", "recovered"),
    [
        ("failed", 1, timedelta(minutes=10), True),  # back-off for attempt 1 is 4 min
        ("failed", 3, timedelta(minutes=10), False),  # ... for attempt 3 it is 16 min
        ("failed", 5, timedelta(days=1), False),  # out of attempts
        ("processing", 1, timedelta(minutes=30), True),  # interrupted (e.g. server restart)
        ("processing", 1, timedelta(minutes=2), False),  # probably still running
        ("pending", 0, timedelta(minutes=10), True),  # the original background task never ran
        ("pending", 0, timedelta(seconds=30), False),
    ],
)
async def test_sweep_recovers_exactly_the_cases_that_need_it(client, fake_ai, status, attempts, age, recovered):
    case = await make_case(client, fake_ai)
    await force_state(case["case_id"], status, attempts, age)
    calls_before = len(fake_ai.calls)

    count = await maintenance.recover_stalled_analyses()

    assert count == (1 if recovered else 0)
    async with open_session() as db:
        beacon = (await db.execute(select(Beacon))).scalar_one()
    assert (beacon.analysis_status == "completed") is recovered
    assert (len(fake_ai.calls) > calls_before) is recovered


# ======================================================================================
# Maintenance: legacy plaintext secret keys
# ======================================================================================
async def legacy_case(client, fake_ai, *, plaintext: str | None, hashed: str | None) -> dict:
    case = await make_case(client, fake_ai)
    async with open_session() as db:
        await db.execute(update(Beacon).where(Beacon.case_id == case["case_id"]).values(secret_key=plaintext, secret_key_hash=hashed))
        await db.commit()
    return case


async def test_scrub_removes_plaintext_when_a_matching_hash_exists(client, fake_ai):
    case = await legacy_case(client, fake_ai, plaintext="A1B2-C3D4", hashed=LEGACY_PBKDF2)
    assert await maintenance.scrub_plaintext_secret_keys() == 1
    async with open_session() as db:
        beacon = (await db.execute(select(Beacon))).scalar_one()
    assert beacon.secret_key is None and beacon.secret_key_hash == LEGACY_PBKDF2, "existing hash kept as is"
    assert (await client.post(f"{API}/public/track", json={"case_id": case["case_id"], "secret_key": "a1b2c3d4"})).status_code == 200
    assert await maintenance.scrub_plaintext_secret_keys() == 0, "idempotent"


async def test_scrub_derives_a_hash_when_only_plaintext_existed(client, fake_ai):
    case = await legacy_case(client, fake_ai, plaintext="9F3E-0B7A", hashed=None)
    await maintenance.scrub_plaintext_secret_keys()
    async with open_session() as db:
        beacon = (await db.execute(select(Beacon))).scalar_one()
    assert beacon.secret_key is None and security.verify_secret("9F3E-0B7A", beacon.secret_key_hash)
    assert (await client.post(f"{API}/public/track", json={"case_id": case["case_id"], "secret_key": "9f3e-0b7a"})).status_code == 200


async def test_unscrubbed_legacy_rows_can_still_authenticate_and_get_upgraded(client, fake_ai):
    case = await legacy_case(client, fake_ai, plaintext="9F3E-0B7A", hashed=None)
    response = await client.post(f"{API}/public/track", json={"case_id": case["case_id"], "secret_key": "9F3E-0B7A"})
    assert response.status_code == 200
    async with open_session() as db:
        beacon = (await db.execute(select(Beacon))).scalar_one()
    assert beacon.secret_key is None and beacon.secret_key_hash
    assert (await client.post(f"{API}/public/track", json={"case_id": case["case_id"], "secret_key": "0000-0000"})).status_code == 401


# ======================================================================================
# Maintenance: uncollected credentials
# ======================================================================================
async def test_uncollected_credentials_expire_after_24_hours(client, fake_ai):
    session = await new_session(client)
    await run_full_intake(client, fake_ai, session)
    async with open_session() as db:
        state = (await db.execute(select(ReportStateTracking))).scalar_one()
        data = dict(state.context_data)
        data["credentials"] = {**data["credentials"], "issued_at": (utc_now() - timedelta(hours=25)).isoformat()}
        state.context_data = data
        await db.commit()

    assert await maintenance.purge_expired_credentials() == 1
    assert (await client.post(f"{API}/public/reports/credentials", json=session.body())).status_code == 404
    async with open_session() as db:
        assert "credentials" not in (await db.execute(select(ReportStateTracking))).scalar_one().context_data


# ======================================================================================
# Track endpoint abuse protection
# ======================================================================================
async def test_guessing_secret_keys_gets_the_client_locked_out(client, fake_ai, enable_rate_limits):
    case = await make_case(client, fake_ai)
    for guess in range(15):
        response = await client.post(f"{API}/public/track", json={"case_id": case["case_id"], "secret_key": f"AAAA-BBBB-CCCC-{guess:04d}"})
        assert response.status_code == 401
    blocked = await client.post(f"{API}/public/track", json={"case_id": case["case_id"], "secret_key": case["secret_key"]})
    assert blocked.status_code == 429 and blocked.json()["code"] == "rate_limited" and "retry-after" in blocked.headers


async def test_unknown_and_known_case_ids_are_indistinguishable(client, fake_ai):
    case = await make_case(client, fake_ai)
    wrong_key = await client.post(f"{API}/public/track", json={"case_id": case["case_id"], "secret_key": "AAAA-BBBB-CCCC-DDDD"})
    wrong_id = await client.post(f"{API}/public/track", json={"case_id": "BCN100000000999", "secret_key": "AAAA-BBBB-CCCC-DDDD"})
    assert wrong_key.status_code == wrong_id.status_code == 401
    assert wrong_key.json() == wrong_id.json()


async def test_the_chat_endpoint_is_rate_limited_per_client_and_per_report(client, fake_ai, enable_rate_limits):
    from tests.helpers import say

    session = await new_session(client)
    statuses = [(await say(client, session, f"message {i}")).status_code for i in range(48)]
    assert statuses[:45] == [200] * 45 and set(statuses[45:]) == {429}
    assert settings.RATE_LIMIT_ENABLED
