"""Evidence upload validation, privacy of stored files, and signed downloads."""

import io
import time

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import sign_file_ref
from app.db.session import open_session
from app.models.report import Evidence
from app.services.file_types import safe_display_name, sniff
from app.services.storage_service import StorageService, parse_ref, ref_in_folder
from tests.fake_ai import turn
from tests.helpers import API, admin_headers, new_session, run_full_intake, same_pixels, say, upload

WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"


def jpeg_with_exif() -> bytes:
    image = Image.new("RGB", (80, 60), (10, 120, 200))
    exif = Image.Exif()
    exif[0x010F], exif[0x0110], exif[0x013B] = "SecretPhoneBrand", "Model-X", "Reporter Name"  # Make, Model, Artist
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


# ======================================================================================
# What is accepted
# ======================================================================================
@pytest.mark.parametrize(
    ("data", "mime"),
    [
        (b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png"),
        (b"\xff\xd8\xff\xe0" + b"0" * 20, "image/jpeg"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        (WAV, "audio/wav"),
        (b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"0" * 10, "audio/mp3"),
        (b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00", "audio/m4a"),
        (b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00", "image/heic"),
        (b"OggS\x00\x02" + b"0" * 10, "audio/ogg"),
        (PDF, "application/pdf"),
        ("Plain notes, with ünïcode ✓".encode(), "text/plain"),
    ],
)
def test_sniffing_identifies_allowed_types(data, mime):
    assert sniff(data).mime == mime


@pytest.mark.parametrize(
    "data",
    [b"MZ\x90\x00\x03\x00\x00\x00", b"\x7fELF\x02\x01\x01", b"PK\x03\x04" + b"0" * 30, b"\x00\x01\x02\x03" * 50, b"ab", b""],
)
def test_sniffing_rejects_executables_archives_and_binary_junk(data):
    assert sniff(data) is None


def test_display_names_are_sanitised_and_match_the_real_type():
    png = sniff(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    assert safe_display_name("../../etc/passwd", png) == "passwd.png"
    assert safe_display_name("report<script>.exe", png) == "report_script.png"
    assert safe_display_name("C:\\Users\\me\\IMG 001 (1).JPG", png) == "IMG 001 (1).png"
    assert safe_display_name("", png) == "evidence.png" and safe_display_name(None, png) == "evidence.png"
    assert safe_display_name("\x00\x01\u202e.png", png).endswith(".png")


def test_storage_references():
    assert parse_ref("supastorage://evidence/reports/abc/1.png") == ("supastorage", "evidence", "reports/abc/1.png")
    assert parse_ref("supastorage://evidence/2026/10/uuid_my file (1).png"), "legacy names with spaces stay readable"
    for bad in (
        "supastorage://evidence/../secret",
        "http://x/y",
        "local://evidence/a/../b",
        "supastorage://evidence/a?b",
        "",
        "local://evidence/",
    ):
        assert parse_ref(bad) is None
    assert ref_in_folder("local://evidence/track/BCN1/a.png", "track/BCN1")
    assert not ref_in_folder("local://evidence/track/BCN10/a.png", "track/BCN1"), "prefix must match a whole folder"


# ======================================================================================
# Upload endpoint
# ======================================================================================
async def test_upload_requires_a_real_session_token(client, png_bytes):
    session = await new_session(client)
    wrong = type(session)(session.report_id, "tk_" + "z" * 43)
    assert (await upload(client, wrong, png_bytes)).status_code == 401
    before = (await client.get("/health")).status_code
    assert before == 200


async def test_valid_upload_is_stored_with_sanitised_metadata(client, png_bytes):
    session = await new_session(client)
    response = await upload(client, session, png_bytes, name="../../evil name<>.html")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mime_type"] == "image/png" and body["file_name"] == "evil name.png" and len(body["hash"]) == 64
    async with open_session() as db:
        evidence = (await db.execute(select(Evidence))).scalar_one()
        assert evidence.file_path.startswith("local://evidence/reports/") and evidence.file_path.endswith(".png")
        assert "evil" not in evidence.file_path, "the client's file name never reaches the storage path"
        stored = await StorageService.download(evidence.file_path)
        assert same_pixels(stored, png_bytes)


async def test_fake_extension_does_not_fool_the_upload(client):
    session = await new_session(client)
    exe = await upload(client, session, b"MZ\x90\x00\x03\x00\x00\x00" + b"0" * 100, name="holiday.png")
    assert exe.status_code == 415 and exe.json()["code"] == "unsupported_file_type"
    assert (await upload(client, session, b"", name="empty.png")).status_code == 422


async def test_html_upload_is_treated_as_inert_text(client):
    session = await new_session(client)
    response = await upload(client, session, b"<html><script>alert(1)</script></html>", name="page.html")
    assert response.status_code == 200 and response.json()["mime_type"] == "text/plain" and response.json()["file_name"].endswith(".txt")


async def test_photo_metadata_is_removed_before_storage(client):
    session = await new_session(client)
    original = jpeg_with_exif()
    assert dict(Image.open(io.BytesIO(original)).getexif()), "test image really has EXIF"
    assert (await upload(client, session, original, name="photo.jpg")).status_code == 200
    async with open_session() as db:
        stored = await StorageService.download((await db.execute(select(Evidence))).scalar_one().file_path)
    exif = dict(Image.open(io.BytesIO(stored)).getexif())
    assert not exif, f"device / author data must not be stored: {exif}"
    assert Image.open(io.BytesIO(stored)).size == (80, 60)


async def test_size_limit_is_enforced_while_streaming(client, monkeypatch):
    session = await new_session(client)
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 4096)
    too_big = b"\x89PNG\r\n\x1a\n" + b"0" * 5000
    response = await upload(client, session, too_big)
    assert response.status_code == 413 and response.json()["code"] == "file_too_large"


async def test_absurd_bodies_are_cut_off_by_the_asgi_limit(client):
    session = await new_session(client)
    huge = b"\x89PNG\r\n\x1a\n" + b"0" * (11 * 1024 * 1024)
    response = await upload(client, session, huge)
    assert response.status_code == 413 and response.json()["code"] == "payload_too_large"


async def test_file_count_cap_and_closed_after_submission(client, fake_ai, png_bytes, monkeypatch):
    monkeypatch.setattr(settings, "MAX_EVIDENCE_FILES_PER_REPORT", 2)
    session = await new_session(client)
    for i in range(2):
        assert (await upload(client, session, png_bytes + bytes([i]), name=f"{i}.png")).status_code == 200
    third = await upload(client, session, png_bytes + b"3")
    assert third.status_code == 409 and third.json()["code"] == "too_many_files"

    await run_full_intake(client, fake_ai, session)
    closed = await upload(client, session, png_bytes + b"4")
    assert closed.status_code == 409 and closed.json()["code"] == "report_submitted"
    async with open_session() as db:
        assert (await db.execute(select(func.count()).select_from(Evidence))).scalar_one() == 2


# ======================================================================================
# Evidence in the conversation + signed downloads
# ======================================================================================
async def test_uploaded_image_is_described_to_the_chat_and_reaches_the_admin(client, fake_ai, png_bytes):
    session = await new_session(client)
    assert (await upload(client, session, png_bytes, name="bribe.png")).status_code == 200
    fake_ai.chat_script[:] = [turn("Thank you, I can see the photo. Where did this happen?", asked="where", what="bribe")]
    await say(client, session, "I have a photo of it")

    chat_calls = [c for c in fake_ai.calls if c["task"] == "chat"]
    prompt = chat_calls[-1]["payload"]["contents"][-1]["parts"][0]["text"]
    assert "<evidence_notes>" in prompt and "uniformed officer" in prompt, "the model is told what the image shows (as untrusted data)"
    assert "UPLOADED FILES: 1" in chat_calls[-1]["payload"]["systemInstruction"]["parts"][0]["text"]

    final = await run_full_intake(client, fake_ai, session)  # background analysis runs after submission
    headers = await admin_headers(client)
    case = (await client.get(f"{API}/admin/reports/", headers=headers)).json()[0]
    detail = (await client.get(f"{API}/admin/reports/{case['id']}", headers=headers)).json()
    evidence = detail["evidence_files"][0]
    assert evidence["file_name"] == "bribe.png" and evidence["analyzed"] and "officer" in evidence["summary"]
    assert evidence["full_url"].startswith(f"{API}/files?ref=") and "local%3A%2F%2F" in evidence["full_url"]
    assert "file_path" not in evidence, "storage references are not exposed"

    # the signed link serves the file, inline, with hardened headers
    download = await client.get(evidence["full_url"])
    assert download.status_code == 200 and same_pixels(download.content, png_bytes)
    assert download.headers["content-type"] == "image/png" and download.headers["content-disposition"].startswith("inline")
    assert download.headers["x-content-type-options"] == "nosniff"
    assert final["case_id"] == detail["case_id"]


async def test_download_links_cannot_be_forged_or_replayed_after_expiry(client, png_bytes):
    session = await new_session(client)
    await upload(client, session, png_bytes)
    async with open_session() as db:
        ref = (await db.execute(select(Evidence))).scalar_one().file_path
    link = StorageService.signed_path(ref, ttl=60)
    assert (await client.get(link)).status_code == 200

    assert (await client.get(link[:-3] + "AAA")).status_code == 403, "tampered signature"
    exp = int(time.time()) - 1
    expired = f"{API}/files?ref={ref}&exp={exp}&sig={sign_file_ref(ref, exp)}"
    assert (await client.get(expired)).status_code == 403, "expired link"
    other_ref = ref.replace("reports", "secrets")
    assert (
        await client.get(f"{API}/files?ref={other_ref}&exp={int(time.time()) + 60}&sig={sign_file_ref(ref, int(time.time()) + 60)}")
    ).status_code == 403
    assert (await client.get(f"{API}/files?ref={ref}")).status_code == 422, "missing signature parameters"


async def test_audio_evidence_is_transcribed_by_the_background_analysis(client, fake_ai):
    session = await new_session(client)
    assert (await upload(client, session, WAV, name="call.wav")).status_code == 200
    await run_full_intake(client, fake_ai, session)

    assert "transcribe" in fake_ai.tasks()
    scoring_prompt = [c for c in fake_ai.calls if c["task"] == "scoring"][-1]["payload"]["contents"][0]["parts"][0]["text"]
    assert "Give me five hundred rupees." in scoring_prompt, "transcripts now actually reach the scorer"
    headers = await admin_headers(client)
    case = (await client.get(f"{API}/admin/reports/", headers=headers)).json()[0]
    assert case["analysis_status"] == "completed"
