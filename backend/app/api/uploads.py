"""Upload handling shared by the reporter, tracking and admin endpoints."""

import hashlib
from dataclasses import dataclass

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import AppError
from app.services.file_types import DetectedFile, safe_display_name, sniff, strip_image_metadata
from app.services.storage_service import StorageError, StorageService, StoredObject


@dataclass
class ValidatedUpload:
    content: bytes
    detected: DetectedFile
    display_name: str
    sha256: str


async def read_limited(file: UploadFile, limit: int | None = None) -> bytes:
    """Read an upload in chunks and stop as soon as it exceeds the limit (never buffer an unbounded body)."""
    limit = limit or settings.MAX_UPLOAD_BYTES
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise AppError(413, "file_too_large", f"Files can be at most {limit // (1024 * 1024)} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


async def validate_upload(file: UploadFile) -> ValidatedUpload:
    content = await read_limited(file)
    if not content:
        raise AppError(422, "empty_file", "The file is empty.")
    detected = sniff(content)
    if detected is None:
        raise AppError(
            415,
            "unsupported_file_type",
            "This file type is not supported. Please upload photos, PDFs, Word documents, text or audio recordings.",
        )
    content = strip_image_metadata(content, detected)  # location / device data in photos could identify the reporter
    return ValidatedUpload(
        content=content,
        detected=detected,
        display_name=safe_display_name(file.filename, detected),
        sha256=hashlib.sha256(content).hexdigest(),
    )


async def store_upload(upload: ValidatedUpload, folder: str) -> StoredObject:
    try:
        return await StorageService.upload(
            upload.content, folder=folder, extension=upload.detected.extension, content_type=upload.detected.mime
        )
    except StorageError as exc:
        raise AppError(
            503, "storage_unavailable", "File storage is temporarily unavailable. Please try again in a moment.", retry_after=10
        ) from exc
