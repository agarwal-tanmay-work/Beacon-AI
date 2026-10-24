"""Evidence file storage.

* Production: a **private** Supabase Storage bucket, accessed with the secret / service-role key over plain
  HTTP (the 100+ MB ``supabase`` client library was only ever used for ``download``, with the *anon* key -
  which cannot read private buckets).
* Development / tests: a directory on disk.

Files are never handed out by public URL. API responses carry short-lived HMAC-signed links to
``GET /api/v1/files`` instead (see ``signed_path``), so a leaked link expires and the bucket can stay private.
"""

import asyncio
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx
import structlog

from app.core.config import settings
from app.core.http import SharedHttpClient
from app.core.security import sign_file_ref

logger = structlog.get_logger(__name__)

_FOLDER = re.compile(r"^[A-Za-z0-9/_\-]+$")
_REF = re.compile(r"^(supastorage|local)://([A-Za-z0-9_\-]+)/([^\x00-\x1f\\?#]+)$")


class StorageError(Exception):
    """Storage is unavailable or rejected the operation (details are logged, never shown to clients)."""


class StorageNotFound(StorageError):
    pass


@dataclass(frozen=True)
class StoredObject:
    ref: str
    size_bytes: int


def parse_ref(ref: str) -> tuple[str, str, str] | None:
    """Split ``scheme://bucket/path`` -> ``(scheme, bucket, path)``; ``None`` for anything suspicious."""
    match = _REF.match(ref or "")
    if not match:
        return None
    scheme, bucket, path = match.groups()
    if any(part in ("", ".", "..") for part in path.split("/")):
        return None
    return scheme, bucket, path


def is_storage_ref(value: str) -> bool:
    return parse_ref(value) is not None


def ref_in_folder(ref: str, folder: str) -> bool:
    """True if ``ref`` is a stored object inside ``folder`` (used to stop cross-case attachment references)."""
    parsed = parse_ref(ref)
    return bool(parsed) and parsed[2].startswith(folder.rstrip("/") + "/")


class StorageService:
    _http = SharedHttpClient(timeout=httpx.Timeout(60.0, connect=10.0))

    # ---- backend selection -----------------------------------------------------------
    @staticmethod
    def backend() -> str:
        return settings.resolved_storage_backend

    @classmethod
    def _scheme(cls) -> str:
        return "supastorage" if cls.backend() == "supabase" else "local"

    @staticmethod
    def _local_root() -> Path:
        return Path(settings.LOCAL_STORAGE_DIR).resolve()

    @classmethod
    def _local_path(cls, bucket: str, path: str) -> Path:
        root = cls._local_root()
        target = (root / bucket / path).resolve()
        if root not in target.parents:  # path traversal guard
            raise StorageError("invalid storage path")
        return target

    # ---- supabase helpers ------------------------------------------------------------
    @staticmethod
    def _supabase_headers(content_type: str | None = None) -> dict[str, str]:
        key = settings.supabase_key
        if not key or not settings.SUPABASE_URL:
            raise StorageError("Supabase storage is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)")
        headers = {"apikey": key}
        if key.startswith("eyJ"):  # legacy JWT keys are also valid Bearer tokens; new sb_secret_ keys are NOT
            headers["Authorization"] = f"Bearer {key}"
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    @staticmethod
    def _object_url(bucket: str, path: str) -> str:
        return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{quote(bucket)}/{quote(path, safe='/')}"  # type: ignore[union-attr]

    @classmethod
    async def _ensure_private_bucket(cls) -> None:
        response = await cls._http.get().post(
            f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/bucket",  # type: ignore[union-attr]
            headers={**cls._supabase_headers("application/json")},
            json={"id": settings.STORAGE_BUCKET, "name": settings.STORAGE_BUCKET, "public": False},
        )
        if response.status_code not in (200, 201, 409):
            raise StorageError(f"could not create storage bucket (HTTP {response.status_code})")
        logger.info("storage_bucket_created", bucket=settings.STORAGE_BUCKET, status=response.status_code)

    # ---- public API ------------------------------------------------------------------
    @classmethod
    async def upload(cls, content: bytes, *, folder: str, extension: str, content_type: str) -> StoredObject:
        if not _FOLDER.match(folder) or not re.fullmatch(r"\.[a-z0-9]{1,6}", extension):
            raise StorageError("invalid storage target")
        bucket = settings.STORAGE_BUCKET
        path = f"{folder}/{uuid.uuid4().hex}{extension}"  # the client's file name is never part of the path
        ref = f"{cls._scheme()}://{bucket}/{path}"

        if cls.backend() == "local":
            target = cls._local_path(bucket, path)

            def write() -> None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)

            await asyncio.to_thread(write)
            return StoredObject(ref, len(content))

        client = cls._http.get()
        for attempt in (1, 2):
            try:
                response = await client.post(cls._object_url(bucket, path), content=content, headers=cls._supabase_headers(content_type))
            except httpx.HTTPError as exc:
                logger.error("storage_upload_failed", error=type(exc).__name__)
                raise StorageError("storage unreachable") from exc
            if response.status_code in (200, 201):
                return StoredObject(ref, len(content))
            if attempt == 1 and "bucket not found" in response.text.lower():
                await cls._ensure_private_bucket()
                continue
            logger.error("storage_upload_failed", status=response.status_code)
            raise StorageError(f"storage rejected the upload (HTTP {response.status_code})")
        raise StorageError("storage upload failed")

    @classmethod
    async def download(cls, ref: str) -> bytes:
        parsed = parse_ref(ref)
        if not parsed or parsed[1] != settings.STORAGE_BUCKET:
            raise StorageNotFound("unknown storage reference")
        scheme, bucket, path = parsed

        if scheme == "local":
            target = cls._local_path(bucket, path)
            try:
                return await asyncio.to_thread(target.read_bytes)
            except FileNotFoundError as exc:
                raise StorageNotFound("file not found") from exc

        try:
            response = await cls._http.get().get(cls._object_url(bucket, path), headers=cls._supabase_headers())
        except httpx.HTTPError as exc:
            logger.error("storage_download_failed", error=type(exc).__name__)
            raise StorageError("storage unreachable") from exc
        if response.status_code == 200:
            return response.content
        if response.status_code in (400, 404):  # Supabase answers 400 "Object not found" for missing keys
            raise StorageNotFound("file not found")
        logger.error("storage_download_failed", status=response.status_code)
        raise StorageError(f"storage rejected the download (HTTP {response.status_code})")

    @classmethod
    async def delete(cls, ref: str) -> None:
        """Best effort clean-up (e.g. an upload whose database insert failed). Never raises."""
        parsed = parse_ref(ref)
        if not parsed:
            return
        scheme, bucket, path = parsed
        try:
            if scheme == "local":
                await asyncio.to_thread(cls._local_path(bucket, path).unlink, True)
            else:
                await cls._http.get().delete(cls._object_url(bucket, path), headers=cls._supabase_headers())
        except Exception as exc:  # noqa: BLE001
            logger.warning("storage_delete_failed", error=type(exc).__name__)

    @classmethod
    async def aclose(cls) -> None:
        await cls._http.aclose()

    # ---- links -----------------------------------------------------------------------
    @staticmethod
    def signed_path(ref: str, *, ttl: int | None = None) -> str:
        """Relative, expiring link to download ``ref`` through this API. Legacy http(s) URLs pass through."""
        if not ref or ref.startswith(("http://", "https://")) or not parse_ref(ref):
            return ref
        expires = int(time.time()) + (ttl or settings.FILE_URL_TTL_SECONDS)
        return f"{settings.API_V1_STR}/files?ref={quote(ref, safe='')}&exp={expires}&sig={sign_file_ref(ref, expires)}"
