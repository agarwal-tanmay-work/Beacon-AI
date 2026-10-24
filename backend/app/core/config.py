"""Application settings.

Values come from environment variables (Render / Docker) or, for local development,
from ``backend_config.env`` / ``.env`` in the backend directory.

Nothing in here may contain a real credential: secrets are ``SecretStr`` so they are
masked if a settings object is ever printed or logged.
"""

import json
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Values copied verbatim from the *.env.example files must never be accepted as real secrets.
_PLACEHOLDER_SECRETS = {
    "change_this_to_a_secure_random_string",
    "your_32_char_random_secret_key",
    "changeme",
    "secret",
}


def _split_list(value: Any) -> Any:
    """Accept a JSON array (``["a","b"]``), a comma separated string, or a real list."""
    if value is None or isinstance(value, list | tuple):
        return list(value) if value is not None else []
    if not isinstance(value, str):
        return value
    raw = value.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            raw = raw.strip("[]")
    return [item.strip().strip("\"'") for item in raw.split(",") if item.strip().strip("\"'")]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=("backend_config.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # unknown / legacy variables (GROQ_API_KEY, SUPABASE_KEY, ...) must not crash startup
    )

    # --- General -----------------------------------------------------------------
    PROJECT_NAME: str = "Beacon AI"
    ENVIRONMENT: str = "production"
    API_V1_STR: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    # Interactive API docs list every admin endpoint, so they are off in production unless explicitly enabled.
    ENABLE_API_DOCS: bool | None = None

    # --- Security ----------------------------------------------------------------
    SECRET_KEY: SecretStr
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=5, le=24 * 60)
    # Admin login. There is intentionally NO built-in fallback password: if neither of the two
    # password settings is provided, admin login is disabled (fails closed).
    ADMIN_USERNAME: str = "beaconai"
    ADMIN_PASSWORD_HASH: SecretStr | None = None  # pbkdf2-sha256 ("$pbkdf2-sha256$...") or bcrypt ("$2b$...")
    ADMIN_PASSWORD: SecretStr | None = None  # plaintext alternative; prefer the hash
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    # Read the client IP from X-Forwarded-For (needed behind Render / Vercel for rate limiting).
    TRUST_PROXY_HEADERS: bool = True
    RATE_LIMIT_ENABLED: bool = True

    # --- Database ----------------------------------------------------------------
    DATABASE_URL: str
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=100)
    # "require" = encrypted but unverified (what Supabase poolers need out of the box);
    # "verify-full" validates the server certificate (optionally against DB_SSL_CA_FILE);
    # "disable" is only for a local Postgres.
    DB_SSL_MODE: Literal["auto", "require", "verify-full", "disable"] = "auto"
    DB_SSL_CA_FILE: str | None = None
    # Resolve the DB host to an IPv4 address up-front (Render cannot reach Supabase over IPv6).
    DB_FORCE_IPV4: bool = True

    # --- Storage (evidence files) ------------------------------------------------
    STORAGE_BACKEND: Literal["auto", "supabase", "local"] = "auto"
    STORAGE_BUCKET: str = "evidence"
    SUPABASE_URL: str | None = None
    # Accepts the legacy JWT service_role key *or* the new "sb_secret_..." key.
    SUPABASE_SERVICE_ROLE_KEY: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"),
    )
    LOCAL_STORAGE_DIR: str = ".local_storage"  # development / tests only
    FILE_URL_TTL_SECONDS: int = Field(default=900, ge=30, le=24 * 3600)

    # --- Uploads / input limits --------------------------------------------------
    MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, ge=1024)
    MAX_EVIDENCE_FILES_PER_REPORT: int = Field(default=10, ge=1)
    MAX_MESSAGE_CHARS: int = Field(default=4000, ge=100)
    MAX_MESSAGES_PER_REPORT: int = Field(default=200, ge=10)

    # --- Gemini ------------------------------------------------------------------
    GEMINI_API_KEY: SecretStr | None = None
    GEMINI_API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    # Optional ordered overrides. Empty = use the built-in chains (see services/gemini/registry.py).
    GEMINI_MODELS: Annotated[list[str], NoDecode] = []
    GEMINI_FAST_MODELS: Annotated[list[str], NoDecode] = []
    GEMINI_AUTO_DISCOVER: bool = True  # ask the API which models exist and adapt the chain
    GEMINI_MAX_CONCURRENCY: int = Field(default=6, ge=1, le=64)

    # --- Background analysis -----------------------------------------------------
    ANALYSIS_SWEEP_INTERVAL_SECONDS: int = Field(default=600, ge=30)
    ANALYSIS_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)

    @field_validator("CORS_ORIGINS", "GEMINI_MODELS", "GEMINI_FAST_MODELS", mode="before")
    @classmethod
    def _parse_lists(cls, value: Any) -> Any:
        return _split_list(value)

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_placeholder_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().strip()
        if not raw:
            raise ValueError("SECRET_KEY must not be empty")
        if raw.lower() in _PLACEHOLDER_SECRETS:
            raise ValueError(
                'SECRET_KEY is still the example placeholder - generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return value

    @field_validator("GEMINI_API_KEY", "ADMIN_PASSWORD", "ADMIN_PASSWORD_HASH", "SUPABASE_SERVICE_ROLE_KEY", mode="before")
    @classmethod
    def _empty_secret_is_none(cls, value: Any) -> Any:
        # `GEMINI_API_KEY=""` in an env file should mean "not configured", not "configured as empty".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # --- Derived helpers -----------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    @property
    def docs_enabled(self) -> bool:
        return self.ENABLE_API_DOCS if self.ENABLE_API_DOCS is not None else not self.is_production

    @property
    def gemini_api_key(self) -> str | None:
        return self.GEMINI_API_KEY.get_secret_value().strip() if self.GEMINI_API_KEY else None

    @property
    def secret_key(self) -> str:
        return self.SECRET_KEY.get_secret_value()

    @property
    def supabase_key(self) -> str | None:
        return self.SUPABASE_SERVICE_ROLE_KEY.get_secret_value().strip() if self.SUPABASE_SERVICE_ROLE_KEY else None

    @property
    def weak_secret_key(self) -> bool:
        return len(self.secret_key) < 32

    @property
    def resolved_storage_backend(self) -> Literal["supabase", "local"]:
        if self.STORAGE_BACKEND != "auto":
            return self.STORAGE_BACKEND  # type: ignore[return-value]
        return "supabase" if (self.SUPABASE_URL and self.supabase_key) else "local"


settings = Settings()  # type: ignore[call-arg]  # required fields come from the environment
