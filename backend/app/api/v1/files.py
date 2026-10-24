"""Serves stored files through short-lived signed links (the storage bucket itself stays private)."""

import re

from fastapi import APIRouter
from fastapi.responses import Response

from app.core.exceptions import AppError
from app.core.security import verify_file_signature
from app.services.file_types import sniff
from app.services.storage_service import StorageError, StorageNotFound, StorageService, parse_ref

router = APIRouter()


@router.get("/files")
async def download_file(ref: str, exp: int, sig: str) -> Response:
    if not verify_file_signature(ref, exp, sig):
        raise AppError(403, "link_expired", "This download link is invalid or has expired. Reload the page to get a fresh one.")
    parsed = parse_ref(ref)
    if parsed is None:
        raise AppError(404, "file_not_found", "File not found.")
    try:
        content = await StorageService.download(ref)
    except StorageNotFound as exc:
        raise AppError(404, "file_not_found", "File not found.") from exc
    except StorageError as exc:
        raise AppError(503, "storage_unavailable", "File storage is temporarily unavailable.", retry_after=10) from exc

    # The type comes from the bytes, never from the stored name: images / audio / PDF open in the browser,
    # everything else downloads. nosniff + a locked-down CSP are added for all responses by middleware.
    detected = sniff(content)
    inline = bool(detected and detected.inline_safe)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", parsed[2].rsplit("/", 1)[-1]) or "file"
    return Response(
        content=content,
        media_type=detected.mime if detected else "application/octet-stream",
        headers={
            "Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{name}"',
            "Cache-Control": "private, max-age=300",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        },
    )
