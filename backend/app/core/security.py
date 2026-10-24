"""Hashing, tokens, signed URLs and admin authentication primitives.

``passlib`` is unmaintained and breaks with recent ``bcrypt`` releases, so it is no longer a
dependency. Hashes it produced are still verified here:

  * ``$pbkdf2-sha256$<rounds>$<salt>$<checksum>``  (secret keys of existing cases)
  * ``$2a$ / $2b$ / $2y$``                         (an ADMIN_PASSWORD_HASH created per the old README)
"""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"
PBKDF2_ROUNDS = 210_000
_PBKDF2_PREFIX = "$pbkdf2-sha256$"

# Crockford base32 without the ambiguous I, L, O, U -> 32 symbols, 5 bits each.
_SECRET_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CROCKFORD_FIXES = str.maketrans({"O": "0", "I": "1", "L": "1"})


# --------------------------------------------------------------------------------------
# Constant-time helpers
# --------------------------------------------------------------------------------------
def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# --------------------------------------------------------------------------------------
# JWT (admin sessions)
# --------------------------------------------------------------------------------------
def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    claims = {"sub": str(subject), "iat": now, "exp": expire}
    return jwt.encode(claims, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises ``jwt.InvalidTokenError`` (including expiry) when the token is not acceptable."""
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )


# --------------------------------------------------------------------------------------
# Password / secret-key hashing
# --------------------------------------------------------------------------------------
def _ab64_encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii").rstrip("=").replace("+", ".")


def _ab64_decode(text: str) -> bytes:
    text = text.replace(".", "+")
    return base64.b64decode(text + "=" * (-len(text) % 4))


def hash_secret(secret: str, *, rounds: int = PBKDF2_ROUNDS) -> str:
    """PBKDF2-HMAC-SHA256 in passlib's ``pbkdf2_sha256`` string format (so old and new hashes mix)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, rounds, dklen=32)
    return f"{_PBKDF2_PREFIX}{rounds}${_ab64_encode(salt)}${_ab64_encode(digest)}"


def _verify_pbkdf2(secret: str, hashed: str) -> bool:
    try:
        _, _, rounds_s, salt_s, checksum_s = hashed.split("$")
        rounds = int(rounds_s)
        salt = _ab64_decode(salt_s)
        expected = _ab64_decode(checksum_s)
        if not 1 <= rounds <= 10_000_000 or not expected:
            return False
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, rounds, dklen=len(expected))
    return hmac.compare_digest(actual, expected)


def _verify_bcrypt(secret: str, hashed: str) -> bool:
    try:
        # bcrypt only ever looks at the first 72 bytes; newer releases raise instead of truncating.
        return bcrypt.checkpw(secret.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def verify_secret(secret: str, hashed: str | None) -> bool:
    """Verify against a pbkdf2-sha256 or bcrypt hash. Never raises; malformed hashes just fail."""
    if not secret or not hashed:
        return False
    hashed = hashed.strip()
    if hashed.startswith(_PBKDF2_PREFIX):
        return _verify_pbkdf2(secret, hashed)
    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        return _verify_bcrypt(secret, hashed)
    return False


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_secret("beacon-timing-equaliser")


def burn_verification_time() -> None:
    """Spend the same CPU as a real verification so unknown IDs are not distinguishable by timing."""
    verify_secret("not-the-secret", _dummy_hash())


# --------------------------------------------------------------------------------------
# Report-session access tokens (reporter, anonymous)
# --------------------------------------------------------------------------------------
def generate_access_token() -> str:
    return "tk_" + secrets.token_urlsafe(32)


def hash_access_token(token: str) -> str:
    # The token is 256 bits of randomness, so a plain SHA-256 is the right tool (no stretching needed).
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_access_token(token: str, expected_hash: str | None) -> bool:
    if not token or not expected_hash:
        return False
    return hmac.compare_digest(hash_access_token(token), expected_hash)


# --------------------------------------------------------------------------------------
# Case ID / secret key (reporter, anonymous follow-up)
# --------------------------------------------------------------------------------------
def generate_case_secret() -> str:
    """16 symbols x 5 bits = 80 bits of entropy, shown as XXXX-XXXX-XXXX-XXXX."""
    raw = "".join(secrets.choice(_SECRET_ALPHABET) for _ in range(16))
    return "-".join(raw[i : i + 4] for i in range(0, 16, 4))


def normalize_case_secret(value: str) -> str:
    """Canonical form for typed-in keys: tolerant of case, spaces, missing dashes and I/L/O typos.

    Works for both the new 16-symbol keys and the legacy 8-hex-digit ``XXXX-XXXX`` keys.
    """
    cleaned = "".join(ch for ch in (value or "").upper() if ch.isalnum()).translate(_CROCKFORD_FIXES)
    if len(cleaned) in (8, 16):
        return "-".join(cleaned[i : i + 4] for i in range(0, len(cleaned), 4))
    return cleaned


def normalize_case_id(value: str) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


# --------------------------------------------------------------------------------------
# Signed file URLs (evidence is never publicly addressable)
# --------------------------------------------------------------------------------------
def _file_signing_key() -> bytes:
    return hmac.new(settings.secret_key.encode("utf-8"), b"beacon-file-url-v1", hashlib.sha256).digest()


def sign_file_ref(ref: str, expires_at: int) -> str:
    mac = hmac.new(_file_signing_key(), f"{ref}|{expires_at}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def verify_file_signature(ref: str, expires_at: int, signature: str, now: int | None = None) -> bool:
    if (now if now is not None else int(datetime.now(UTC).timestamp())) > expires_at:
        return False
    return hmac.compare_digest(sign_file_ref(ref, expires_at), signature)


# --------------------------------------------------------------------------------------
# Admin credentials
# --------------------------------------------------------------------------------------
def admin_login_configured() -> bool:
    return bool(settings.ADMIN_PASSWORD_HASH or settings.ADMIN_PASSWORD)


def admin_subject() -> str:
    return settings.ADMIN_USERNAME.strip().lower()


def verify_admin_credentials(username: str, password: str) -> bool:
    """Constant-time check of the configured admin account. Fails closed when nothing is configured."""
    if not admin_login_configured():
        return False

    user = (username or "").strip().lower()
    valid_users = {admin_subject(), "admin"}  # "admin" is the long-standing alias
    user_ok = any(hmac.compare_digest(user.encode(), candidate.encode()) for candidate in valid_users)

    password_ok = False
    if settings.ADMIN_PASSWORD_HASH:
        password_ok = verify_secret(password, settings.ADMIN_PASSWORD_HASH.get_secret_value())
    elif settings.ADMIN_PASSWORD:
        password_ok = constant_time_equals(password, settings.ADMIN_PASSWORD.get_secret_value())

    return user_ok and password_ok
