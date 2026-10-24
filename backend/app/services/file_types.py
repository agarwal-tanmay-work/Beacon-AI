"""What may be uploaded - decided from the file's bytes, never from the client's claims.

Only a short allowlist is accepted (photos, scans, recordings, documents). Anything else - executables,
HTML, SVG, scripts, archives - is rejected, which also removes the stored-XSS / content-sniffing risk of
serving user files back from the API.
"""

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass

import structlog

from app.schemas.ai import EvidenceKind

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DetectedFile:
    mime: str
    kind: str  # EvidenceKind.*
    extension: str  # with leading dot

    @property
    def inline_safe(self) -> bool:
        """Types a browser may render itself when opened from a signed URL."""
        return self.kind in (EvidenceKind.IMAGE, EvidenceKind.AUDIO) or self.mime == "application/pdf"


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1", b"heif"}
_M4A_BRANDS = {b"M4A ", b"M4B ", b"mp42", b"mp41", b"isom", b"f4a ", b"dash", b"iso2", b"M4P "}


def _image(mime: str, ext: str) -> DetectedFile:
    return DetectedFile(mime, EvidenceKind.IMAGE, ext)


def _audio(mime: str, ext: str) -> DetectedFile:
    return DetectedFile(mime, EvidenceKind.AUDIO, ext)


def _is_docx(content: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:  # reads only the central directory
            return "word/document.xml" in archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def _looks_like_text(content: bytes) -> bool:
    sample = content[:65536]
    if b"\x00" in sample:
        return False
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError as exc:
        if exc.start < len(sample) - 4:  # a multi-byte character cut by the sample boundary is fine
            return False
        text = sample[: exc.start].decode("utf-8", errors="ignore")
    if not text.strip():
        return False
    control = sum(1 for ch in text if unicodedata.category(ch) == "Cc" and ch not in "\n\r\t")
    return control / len(text) < 0.01


def sniff(content: bytes) -> DetectedFile | None:
    """Identify an allowed file type from its bytes, or ``None`` if it is not allowed."""
    head = content[:16]
    if len(content) < 4:
        return None
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return _image("image/png", ".png")
    if head.startswith(b"\xff\xd8\xff"):
        return _image("image/jpeg", ".jpg")
    if head.startswith((b"GIF87a", b"GIF89a")):
        return _image("image/gif", ".gif")
    if head[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return _image("image/webp", ".webp")
    if head[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return _audio("audio/wav", ".wav")
    if content[4:8] == b"ftyp":
        brand = content[8:12]
        if brand in _HEIC_BRANDS:
            return _image("image/heic", ".heic")
        if brand in _M4A_BRANDS:
            return _audio("audio/m4a", ".m4a")
        return None
    if head.startswith(b"%PDF-") or b"%PDF-" in content[:1024]:
        return DetectedFile("application/pdf", EvidenceKind.DOCUMENT, ".pdf")
    if head.startswith(b"OggS"):
        return _audio("audio/ogg", ".ogg")
    if head.startswith(b"fLaC"):
        return _audio("audio/flac", ".flac")
    if head[:4] == b"FORM" and content[8:12] in (b"AIFF", b"AIFC"):
        return _audio("audio/aiff", ".aiff")
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return _audio("audio/webm", ".webm")
    if head.startswith(b"ID3"):
        return _audio("audio/mp3", ".mp3")
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xF6) == 0xF0:  # ADTS frame header
        return _audio("audio/aac", ".aac")
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0 and (head[1] & 0x06) != 0:  # MPEG audio frame sync
        return _audio("audio/mp3", ".mp3")
    if head.startswith(b"PK\x03\x04"):
        return DetectedFile(_DOCX_MIME, EvidenceKind.DOCUMENT, ".docx") if _is_docx(content) else None
    if _looks_like_text(content):
        return DetectedFile("text/plain", EvidenceKind.DOCUMENT, ".txt")
    return None


_UNSAFE = re.compile(r"[^\w.\- ()\[\]]+", re.UNICODE)


def safe_display_name(original: str | None, detected: DetectedFile) -> str:
    """A harmless display name: no path parts, no control characters, extension that matches the real type."""
    name = (original or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFKC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    stem = name.rsplit(".", 1)[0] if "." in name else name
    stem = _UNSAFE.sub("_", stem).strip(" ._-")[:100] or "evidence"
    return f"{stem}{detected.extension}"


def strip_image_metadata(content: bytes, detected: DetectedFile) -> bytes:
    """Remove EXIF / GPS / device information from JPEG, PNG and WebP photos (reporter anonymity).

    Returns the original bytes if the image cannot be re-encoded - never blocks an upload.
    """
    if detected.mime not in ("image/jpeg", "image/png", "image/webp"):
        return content
    try:
        from PIL import Image, ImageOps

        Image.MAX_IMAGE_PIXELS = 60_000_000
        with Image.open(io.BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source)  # bake in the orientation before dropping the tag
            out = io.BytesIO()
            if detected.mime == "image/jpeg":
                image.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
            elif detected.mime == "image/png":
                image.save(out, format="PNG", optimize=True)
            else:
                image.save(out, format="WEBP", quality=92)
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001 - decoder errors, decompression bombs, odd modes ...
        logger.warning("image_metadata_strip_failed", mime=detected.mime, error=type(exc).__name__)
        return content
