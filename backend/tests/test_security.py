"""Crypto primitives, token handling and the abuse limiters."""

import time
from datetime import timedelta

import jwt
import pytest

from app.core import security
from app.core.config import settings
from app.core.rate_limit import FailureLimiter, SlidingWindowLimiter
from tests.gemini_helpers import FakeClock

# Hashes produced by the OLD code (passlib 1.7.4 pbkdf2_sha256 / bcrypt). They must keep verifying.
LEGACY_PBKDF2 = "$pbkdf2-sha256$29000$8p4zxlir9Z4TwjindA7h/A$n0ILWLr4sl72ZViGTfQFvCgY/Z9YVykHHrM8lyU0eLk"  # 'A1B2-C3D4'
LEGACY_PBKDF2_DOTTED = (
    "$pbkdf2-sha256$29000$9D5H6L1XyjkHIKRU6v3//w$WcurM2/uDGlx61Pw.Zkygsqwlp.vZGWSV8FIGe2ZGT8"  # '9F3E-0B7A' ('.' in ab64)
)
LEGACY_BCRYPT = "$2b$04$Nf/wZXbVyKiVBkckpkEABeGNoDBGmCKW2eYTyfwq1r4.nNpzcmO8e"  # 'Admin Pa55word!'


# ======================================================================================
# Hashing
# ======================================================================================
def test_hashes_created_by_the_old_passlib_code_still_verify():
    assert security.verify_secret("A1B2-C3D4", LEGACY_PBKDF2)
    assert security.verify_secret("9F3E-0B7A", LEGACY_PBKDF2_DOTTED)
    assert not security.verify_secret("A1B2-C3D5", LEGACY_PBKDF2)
    assert security.verify_secret("Admin Pa55word!", LEGACY_BCRYPT)
    assert not security.verify_secret("admin pa55word!", LEGACY_BCRYPT)


def test_new_hashes_are_in_passlib_format_and_roundtrip():
    hashed = security.hash_secret("S3cret-Key", rounds=1000)
    assert hashed.startswith("$pbkdf2-sha256$1000$") and security.verify_secret("S3cret-Key", hashed)
    assert hashed != security.hash_secret("S3cret-Key", rounds=1000), "salted"
    passlib = pytest.importorskip("passlib.hash")
    assert passlib.pbkdf2_sha256.verify("S3cret-Key", hashed), "the old code (and tools) can still read new hashes"


@pytest.mark.parametrize(
    "bad",
    ["", None, "plaintext", "$pbkdf2-sha256$abc", "$pbkdf2-sha256$0$x$y", "$2b$04$short", "$2b$", "$pbkdf2-sha256$99999999999$QUJD$QUJD"],
)
def test_malformed_hashes_fail_without_raising(bad):
    assert security.verify_secret("anything", bad) is False


def test_bcrypt_passwords_over_72_bytes_do_not_crash():
    import bcrypt

    long_password = "x" * 100
    hashed = bcrypt.hashpw(long_password.encode()[:72], bcrypt.gensalt(rounds=4)).decode()
    assert security.verify_secret(long_password, hashed)


# ======================================================================================
# Case credentials
# ======================================================================================
def test_case_secret_format_and_entropy():
    keys = {security.generate_case_secret() for _ in range(500)}
    assert len(keys) == 500
    sample = next(iter(keys))
    groups = sample.split("-")
    assert len(groups) == 4 and all(len(g) == 4 for g in groups)
    assert set(sample.replace("-", "")) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


@pytest.mark.parametrize(
    ("typed", "canonical"),
    [
        ("a1b2-c3d4", "A1B2-C3D4"),  # legacy 8-hex key, any case
        ("  a1b2 c3d4 ", "A1B2-C3D4"),
        ("A1B2C3D4", "A1B2-C3D4"),
        ("abcd-efgh-jkmn-pqrs", "ABCD-EFGH-JKMN-PQRS"),
        ("abcdefghjkmnpqrs", "ABCD-EFGH-JKMN-PQRS"),
        ("O1IL-0000-1111-2222", "0111-0000-1111-2222"),  # Crockford: O->0, I/L->1
    ],
)
def test_secret_key_normalisation(typed, canonical):
    assert security.normalize_case_secret(typed) == canonical


def test_case_id_normalisation():
    assert security.normalize_case_id(" bcn 100000000001 ") == "BCN100000000001"


def test_access_token_hashing():
    token = security.generate_access_token()
    assert token.startswith("tk_") and len(token) >= 40
    stored = security.hash_access_token(token)
    assert security.verify_access_token(token, stored)
    assert not security.verify_access_token(token + "x", stored)
    assert not security.verify_access_token("", stored) and not security.verify_access_token(token, None)


# ======================================================================================
# JWT + signed URLs
# ======================================================================================
def test_jwt_roundtrip_and_rejections():
    token = security.create_access_token("beaconai")
    assert security.decode_access_token(token)["sub"] == "beaconai"

    expired = security.create_access_token("beaconai", timedelta(seconds=-5))
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(expired)

    forged = jwt.encode({"sub": "beaconai", "exp": int(time.time()) + 600}, "some-other-secret-key-0123456789abcdef", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        security.decode_access_token(forged)

    unsigned = jwt.encode({"sub": "beaconai", "exp": int(time.time()) + 600}, None, algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(unsigned)  # the 'alg: none' trick

    no_exp = jwt.encode({"sub": "beaconai"}, settings.secret_key, algorithm="HS256")
    with pytest.raises(jwt.MissingRequiredClaimError):
        security.decode_access_token(no_exp)


def test_signed_file_links():
    ref, expires = "local://evidence/reports/abc/file.png", int(time.time()) + 60
    signature = security.sign_file_ref(ref, expires)
    assert security.verify_file_signature(ref, expires, signature)
    assert not security.verify_file_signature(ref + "x", expires, signature), "bound to the file"
    assert not security.verify_file_signature(ref, expires + 1, signature), "bound to the expiry"
    assert not security.verify_file_signature(ref, expires, signature[:-2] + "AA")
    assert not security.verify_file_signature(ref, expires, signature, now=expires + 1), "expired"


# ======================================================================================
# Admin credentials
# ======================================================================================
def test_admin_login_fails_closed_without_any_password(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", None)
    assert security.admin_login_configured() is False
    assert security.verify_admin_credentials("beaconai", "BeaconAI@26") is False, "the old hard-coded password is gone"
    assert security.verify_admin_credentials("admin", "") is False


def test_admin_credentials_plain_and_hashed(monkeypatch):
    from pydantic import SecretStr

    assert security.verify_admin_credentials("BeaconAI", "correct horse battery staple")  # username is case-insensitive
    assert security.verify_admin_credentials("admin", "correct horse battery staple")  # legacy alias
    assert not security.verify_admin_credentials("beaconai", "wrong")
    assert not security.verify_admin_credentials("someone", "correct horse battery staple")

    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", SecretStr(LEGACY_BCRYPT))
    assert security.verify_admin_credentials("beaconai", "Admin Pa55word!")
    assert not security.verify_admin_credentials("beaconai", "correct horse battery staple")


# ======================================================================================
# Limiters
# ======================================================================================
def test_sliding_window_limiter():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(3, 60, clock=clock)
    assert [limiter.hit("a")[0] for _ in range(3)] == [True, True, True]
    allowed, retry = limiter.hit("a")
    assert not allowed and 59 <= retry <= 60
    assert limiter.hit("b")[0], "keys are independent"
    clock.advance(61)
    assert limiter.hit("a")[0], "window slides"


def test_limiter_memory_is_bounded():
    limiter = SlidingWindowLimiter(1, 3600, max_keys=100)
    for i in range(1000):
        limiter.hit(f"ip-{i}")
    assert len(limiter._events) <= 101  # noqa: SLF001


def test_failure_limiter_blocks_then_recovers():
    clock = FakeClock()
    failures = FailureLimiter(3, 900, clock=clock)
    for _ in range(2):
        failures.record_failure("ip")
    assert failures.blocked_for("ip") == 0
    failures.record_failure("ip")
    assert 890 < failures.blocked_for("ip") <= 900
    clock.advance(901)
    assert failures.blocked_for("ip") == 0
