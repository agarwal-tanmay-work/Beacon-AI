"""Turns an uploaded file into text the chat agent and the credibility scorer can use.

One analysis per file, cached on the ``Evidence`` row (``forensic_analysis``):

* images   - quality check (Pillow) + one Gemini vision call for description and visible text,
             local Tesseract OCR as a fallback if no model is reachable;
* audio    - Gemini transcription;
* PDF/DOCX/TXT - text is extracted locally (no AI needed), scanned PDFs fall back to vision on page 1-2.

Compared with the old processor: no OpenCV/numpy colour "heuristics", no second asyncio event loop created
inside a worker thread (it shared one HTTP client across loops), no video/ffmpeg path that the UI never
offered, and transcripts / extracted text now actually reach the scoring prompt.
"""

import asyncio
import html
import io
import re
import shutil
import zipfile
from typing import Any

import structlog

from app.models.report import Evidence
from app.schemas.ai import EvidenceDigest, EvidenceKind
from app.services import ai_service
from app.services.file_types import DetectedFile, sniff
from app.services.gemini import GeminiBlocked, GeminiError
from app.services.storage_service import StorageError, StorageNotFound, StorageService

logger = structlog.get_logger(__name__)

ANALYSIS_VERSION = 1
MAX_TEXT_CHARS = 6000
MAX_DOCX_XML_BYTES = 10 * 1024 * 1024
BLUR_THRESHOLD = 100.0


# ======================================================================================
# Local (CPU) helpers - run in worker threads
# ======================================================================================
def image_quality_notes(content: bytes) -> list[str]:
    try:
        from PIL import Image, ImageFilter, ImageOps, ImageStat

        Image.MAX_IMAGE_PIXELS = 60_000_000
        with Image.open(io.BytesIO(content)) as image:
            notes: list[str] = []
            width, height = image.size
            if min(width, height) < 200:
                notes.append("very_small_image")
            gray = ImageOps.exif_transpose(image).convert("L")
            gray.thumbnail((1024, 1024))
            laplacian = gray.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
            variance = ImageStat.Stat(laplacian).var[0]
            notes.append("blurry_image" if variance < BLUR_THRESHOLD else "sharp_image")
            return notes
    except Exception as exc:  # noqa: BLE001 - unsupported formats (HEIC), bombs, corrupt data
        logger.info("image_quality_check_skipped", error=type(exc).__name__)
        return []


def local_ocr(content: bytes) -> str:
    """Tesseract fallback. Empty string when Tesseract is not installed or finds nothing."""
    if not shutil.which("tesseract"):
        return ""
    try:
        import pytesseract
        from PIL import Image

        with Image.open(io.BytesIO(content)) as image:
            return pytesseract.image_to_string(image, timeout=25).strip()[:MAX_TEXT_CHARS]
    except Exception as exc:  # noqa: BLE001
        logger.info("local_ocr_failed", error=type(exc).__name__)
        return ""


def pdf_text_and_page_image(content: bytes) -> tuple[str, bytes | None, str | None]:
    """Embedded text of the first pages, plus a rendering of page 1 (for scanned PDFs), plus a problem note."""
    try:
        import pymupdf

        with pymupdf.open(stream=content, filetype="pdf") as doc:
            if doc.needs_pass:
                return "", None, "password_protected_pdf"
            pages = min(doc.page_count, 5)
            text = "\n".join(doc[i].get_text() for i in range(pages)).strip()
            image = None
            if len(text) < 40 and doc.page_count:
                image = doc[0].get_pixmap(dpi=110).tobytes("png")
            return text[:MAX_TEXT_CHARS], image, None
    except Exception as exc:  # noqa: BLE001
        logger.info("pdf_extraction_failed", error=type(exc).__name__)
        return "", None, "unreadable_pdf"


def docx_text(content: bytes) -> str:
    """Text of a .docx without an XML parser (user-supplied XML + entity expansion = DoS risk)."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                return ""
            xml = archive.read(info).decode("utf-8", errors="ignore")
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""
    paragraphs = []
    for paragraph in xml.split("</w:p>"):
        runs = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", paragraph)
        if runs:
            paragraphs.append(html.unescape("".join(runs)))
    return "\n".join(paragraphs).strip()[:MAX_TEXT_CHARS]


# ======================================================================================
# Analysis
# ======================================================================================
def _empty_analysis(kind: str) -> dict[str, Any]:
    return {
        "v": ANALYSIS_VERSION,
        "kind": kind,
        "description": "",
        "extracted_text": "",
        "transcript": "",
        "quality_notes": [],
        "analysis_available": False,
        "corrupt": False,
        "ai_used": False,
    }


class EvidenceProcessor:
    @classmethod
    def cached(cls, evidence: Evidence) -> dict[str, Any] | None:
        data = evidence.forensic_analysis
        if isinstance(data, dict) and data.get("v") == ANALYSIS_VERSION and data.get("analysis_available"):
            return data
        return None

    @classmethod
    async def analyze(cls, evidence: Evidence, *, quick: bool = False) -> dict[str, Any]:
        """Analyse (or return the cached analysis of) one file. ``quick`` = chat-time: tight timeouts, no audio."""
        if (cached := cls.cached(evidence)) is not None:
            return cached

        try:
            content = await StorageService.download(evidence.file_path)
        except (StorageNotFound, StorageError) as exc:
            logger.warning("evidence_unavailable", evidence_id=str(evidence.id), error=type(exc).__name__)
            analysis = _empty_analysis(EvidenceKind.UNKNOWN)
            analysis["corrupt"] = isinstance(exc, StorageNotFound)
            return analysis

        detected = sniff(content) if content else None
        if detected is None:
            analysis = _empty_analysis(EvidenceKind.UNKNOWN)
            analysis.update(corrupt=True, analysis_available=True, quality_notes=["empty_or_unrecognised_file"])
            cls._store(evidence, analysis)
            return analysis

        analysis = _empty_analysis(detected.kind)
        try:
            if detected.kind == EvidenceKind.IMAGE:
                await cls._analyze_image(analysis, content, detected, quick=quick)
            elif detected.kind == EvidenceKind.AUDIO:
                await cls._analyze_audio(analysis, content, detected, quick=quick)
            else:
                await cls._analyze_document(analysis, content, detected, quick=quick)
        except GeminiBlocked:
            analysis["quality_notes"].append("analysis_declined_by_ai_safety_filter")
            analysis["analysis_available"] = True  # a definitive outcome - do not retry forever
        except GeminiError as exc:
            logger.warning("evidence_ai_analysis_failed", evidence_id=str(evidence.id), kind=exc.kind)

        if analysis["analysis_available"]:
            cls._store(evidence, analysis)
        return analysis

    @classmethod
    def _store(cls, evidence: Evidence, analysis: dict[str, Any]) -> None:
        evidence.forensic_analysis = dict(analysis)  # new object so SQLAlchemy sees the JSON change
        evidence.object_labels = list(analysis.get("quality_notes") or [])
        evidence.is_scanned = True

    @classmethod
    async def _analyze_image(cls, analysis: dict[str, Any], content: bytes, detected: DetectedFile, *, quick: bool) -> None:
        analysis["quality_notes"] = await asyncio.to_thread(image_quality_notes, content)
        try:
            vision = await ai_service.describe_image(
                content, detected.mime, timeout=12.0 if quick else 25.0, deadline=15.0 if quick else 40.0
            )
            analysis.update(
                description=vision.description, extracted_text=vision.visible_text[:MAX_TEXT_CHARS], ai_used=True, analysis_available=True
            )
            if not vision.legible:
                analysis["quality_notes"].append("not_legible")
        except GeminiBlocked:
            raise
        except GeminiError:
            # No model reachable: keep what we can learn locally. The result is deliberately not final
            # (analysis_available stays False) so the background analysis tries the AI again later.
            analysis["extracted_text"] = await asyncio.to_thread(local_ocr, content)
            raise

    @classmethod
    async def _analyze_audio(cls, analysis: dict[str, Any], content: bytes, detected: DetectedFile, *, quick: bool) -> None:
        if quick:
            analysis["description"] = "Audio recording (will be transcribed after submission)."
            return  # chat stays snappy; not final, so the background analysis transcribes it
        transcript = await ai_service.transcribe_audio(content, detected.mime)
        analysis.update(transcript=transcript, ai_used=True, analysis_available=True)

    @classmethod
    async def _analyze_document(cls, analysis: dict[str, Any], content: bytes, detected: DetectedFile, *, quick: bool) -> None:
        if detected.mime == "application/pdf":
            text, page_image, problem = await asyncio.to_thread(pdf_text_and_page_image, content)
            if problem:
                analysis["quality_notes"].append(problem)
            analysis["extracted_text"] = text
            analysis["analysis_available"] = True
            if not text and page_image:  # scanned PDF: let vision read page 1
                try:
                    vision = await ai_service.describe_image(
                        page_image, "image/png", timeout=12.0 if quick else 25.0, deadline=15.0 if quick else 40.0
                    )
                    analysis.update(description=vision.description, extracted_text=vision.visible_text[:MAX_TEXT_CHARS], ai_used=True)
                except GeminiBlocked:
                    raise
                except GeminiError:
                    analysis["analysis_available"] = False  # retry with AI later
                    raise
        elif detected.mime.endswith("wordprocessingml.document"):
            analysis["extracted_text"] = await asyncio.to_thread(docx_text, content)
            analysis["analysis_available"] = True
        else:
            analysis["extracted_text"] = content.decode("utf-8", errors="replace").strip()[:MAX_TEXT_CHARS]
            analysis["analysis_available"] = True

    # ---- presentation ------------------------------------------------------------------
    @classmethod
    def chat_note(cls, evidence: Evidence, analysis: dict[str, Any]) -> str:
        """One line for the chat model (untrusted content: it is wrapped in <evidence_notes> by the caller)."""
        kind = analysis.get("kind") or EvidenceKind.UNKNOWN
        label = {"image": "Image", "audio": "Audio", "document": "Document"}.get(kind, "File")
        detail = analysis.get("description") or (analysis.get("extracted_text") or "")[:200] or "uploaded, analysis pending"
        return f"{label} '{evidence.file_name}': {' '.join(str(detail).split())[:300]}"

    @classmethod
    def to_digest(cls, evidence: Evidence, analysis: dict[str, Any], *, duplicate: bool) -> EvidenceDigest:
        status = "corrupt" if analysis.get("corrupt") or evidence.size_bytes == 0 else "duplicate" if duplicate else "valid"
        return EvidenceDigest(
            file_name=evidence.file_name,
            kind=analysis.get("kind") or EvidenceKind.UNKNOWN,
            status=status,  # type: ignore[arg-type]
            description=str(analysis.get("description") or ""),
            extracted_text=str(analysis.get("extracted_text") or ""),
            transcript=str(analysis.get("transcript") or ""),
            quality_notes=list(analysis.get("quality_notes") or []),
            analysis_available=bool(analysis.get("analysis_available") or analysis.get("extracted_text")),
        )
