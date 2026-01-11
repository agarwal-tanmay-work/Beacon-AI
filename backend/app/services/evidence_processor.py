
import structlog
import io
import mimetypes
import hashlib
import os
import tempfile
import subprocess
from typing import List, Optional, Set
from app.schemas.ai import EvidenceMetadata, EvidenceType
from app.models.local_models import LocalEvidence

logger = structlog.get_logger()

class EvidenceProcessor:
    """
    Layer 1: Deterministic Preprocessing for Evidence.
    Runs locally before LLM.
    Uses LAZY IMPORTS for heavy ML libraries to ensure fast startup and stability.
    """
    
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB Limit per file

    @classmethod
    def process_evidence(cls, evidence_list: List[LocalEvidence]) -> List[EvidenceMetadata]:
        processed = []
        seen_hashes: Set[str] = set()
        
        for ev in evidence_list:
            logger.info("processing_file", file=ev.file_name)
            meta = cls._analyze_single_file(ev, seen_hashes)
            if meta.file_hash:
                seen_hashes.add(meta.file_hash)
            processed.append(meta)
        return processed

    @classmethod
    def _analyze_single_file(cls, evidence: LocalEvidence, seen_hashes: Set[str]) -> EvidenceMetadata:
        file_path = evidence.file_path
        
        # 0. Basic Validation & File Loading
        try:
            file_size = os.path.getsize(file_path)
            if file_size > cls.MAX_FILE_SIZE:
                return EvidenceMetadata(
                    file_name=evidence.file_name,
                    file_path=file_path,
                    file_type=EvidenceType.UNKNOWN,
                    is_empty_or_corrupt=True,
                    file_size=file_size,
                    object_labels=["error: file too large (>5MB)"]
                )

            with open(file_path, "rb") as f:
                content = f.read()
            
            file_hash = hashlib.sha256(content).hexdigest()
            is_empty = len(content) == 0
            is_duplicate = file_hash in seen_hashes
            
        except (FileNotFoundError, PermissionError) as e:
             return EvidenceMetadata(
                file_name=evidence.file_name,
                file_path=file_path,
                file_type=EvidenceType.UNKNOWN,
                is_empty_or_corrupt=True,
                object_labels=[f"error: {str(e)}"]
            )
            
        file_type = cls._detect_type(content, evidence.file_name)
        
        meta = EvidenceMetadata(
            file_name=evidence.file_name,
            file_path=file_path,
            file_type=file_type,
            is_empty_or_corrupt=is_empty,
            is_duplicate=is_duplicate,
            file_hash=file_hash,
            file_size=file_size
        )
        
        if is_empty or is_duplicate:
            return meta

        # 1. OCR (Images/PDFs)
        if file_type == EvidenceType.IMAGE:
            cls._process_image_ocr(content, meta)
        elif file_type == EvidenceType.DOCUMENT and evidence.file_name.lower().endswith(".pdf"):
            cls._process_pdf_ocr(content, meta)

        # 2. Object Detection (Images/Videos) - OpenCV Basic
        if file_type == EvidenceType.IMAGE:
             cls._process_image_cv(content, meta)
        elif file_type == EvidenceType.VIDEO:
             cls._process_video_cv(content, meta)

        # 3. Audio/Video Transcription (Whisper)
        if file_type in [EvidenceType.AUDIO, EvidenceType.VIDEO]:
            cls._process_media_transcription(content, file_type, meta)
            
        return meta

    @classmethod
    def _process_image_ocr(cls, content: bytes, meta: EvidenceMetadata):
        try:
            import pytesseract
            from PIL import Image
            pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            
            image = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(image)
            if text.strip():
                meta.ocr_text_snippet = text[:500] 
                if len(text.strip()) > 10:
                    meta.has_relevant_keywords = True
        except Exception as e:
            logger.warning("ocr_failed", error=str(e), file=meta.file_name)

    @classmethod
    def _process_pdf_ocr(cls, content: bytes, meta: EvidenceMetadata):
        try:
            # Requires pymupdf (fitz)
            import fitz
            import pytesseract
            from PIL import Image
            
            tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if not os.path.exists(tesseract_path):
                logger.warning("tesseract_not_found", path=tesseract_path)
                return
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            
            # Open PDF
            doc = fitz.open(stream=content, filetype="pdf")
            full_text = ""
            # Process first 3 pages
            for i in range(min(3, len(doc))):
                page = doc.load_page(i)
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img)
                full_text += text + "\n"
            
            if full_text.strip():
                meta.ocr_text_snippet = full_text[:500]
                meta.has_relevant_keywords = len(full_text.strip()) > 20
        except Exception as e:
            logger.warning("pdf_ocr_failed", error=str(e), file=meta.file_name)

    @classmethod
    def _process_image_cv(cls, content: bytes, meta: EvidenceMetadata):
        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                # 1. Blur Detection
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                variance = cv2.Laplacian(gray, cv2.CV_64F).var()
                if variance < 100:
                    meta.object_labels.append("blurry")
                
                # 2. Coarse Contextual Signals (Basic Color/Shape heuristics)
                # Heuristic for "Cash" (Greenish/Yellowish shades)
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                green_mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
                if np.sum(green_mask) > (img.shape[0] * img.shape[1] * 0.1):
                    meta.object_labels.append("signal: possible_currency_colors")
                
                # Heuristic for "Documents" (High contrast white-ish background)
                _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
                if np.sum(binary == 255) > (img.shape[0] * img.shape[1] * 0.4):
                    meta.object_labels.append("signal: possible_document_layout")
        except Exception:
            pass

    @classmethod
    def _process_media_transcription(cls, content: bytes, file_type: EvidenceType, meta: EvidenceMetadata):
        temp_audio_path = None
        try:
            import whisper
            # Set FFmpeg path for Windows
            ffmpeg_dir = r"C:\ffmpeg\bin"
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                if file_type == EvidenceType.AUDIO:
                    tmp.write(content)
                    temp_audio_path = tmp.name
                else:
                    # VIDEO: Extract audio using FFmpeg
                    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_tmp:
                        video_tmp.write(content)
                        video_path = video_tmp.name
                    
                    temp_audio_path = tmp.name
                    # Call FFmpeg to extract audio
                    cmd = [
                        os.path.join(ffmpeg_dir, "ffmpeg.exe"),
                        "-y", "-i", video_path, 
                        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", 
                        temp_audio_path
                    ]
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    os.unlink(video_path)

            model = whisper.load_model("tiny")
            result = model.transcribe(temp_audio_path)
            text = result["text"].strip()
            
            if text:
                meta.audio_transcript_snippet = text[:500]
                meta.has_relevant_keywords = len(text) > 5
            else:
                meta.audio_transcript_snippet = "[Silent or unintelligible]"
        except Exception as e:
            logger.warning("transcription_failed", error=str(e), file=meta.file_name)
            meta.audio_transcript_snippet = f"[Processing Failed: {str(e)}]"
        finally:
            if temp_audio_path and os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)

    @classmethod
    def _process_video_cv(cls, content: bytes, meta: EvidenceMetadata):
        """
        Extract a frame from video to perform basic object detection (context).
        """
        temp_video_path = None
        temp_frame_path = None
        try:
            ffmpeg_dir = r"C:\ffmpeg\bin"
            ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
            
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as v_tmp:
                v_tmp.write(content)
                temp_video_path = v_tmp.name
            
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f_tmp:
                temp_frame_path = f_tmp.name
            
            # Extract frame at 1 second mark (or middle of short video)
            cmd = [
                ffmpeg_exe, "-y", "-i", temp_video_path,
                "-ss", "00:00:01", "-frames:v", "1",
                temp_frame_path
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            
            if os.path.exists(temp_frame_path):
                with open(temp_frame_path, "rb") as f:
                    frame_content = f.read()
                cls._process_image_cv(frame_content, meta)
                
        except Exception as e:
             logger.warning("video_cv_failed", error=str(e), file=meta.file_name)
        finally:
            if temp_video_path and os.path.exists(temp_video_path): os.unlink(temp_video_path)
            if temp_frame_path and os.path.exists(temp_frame_path): os.unlink(temp_frame_path)

    @classmethod
    def _detect_type(cls, content: bytes, filename: str) -> EvidenceType:
        # Prioritize mimetypes on Windows to avoid magic hangs
        mime, _ = mimetypes.guess_type(filename)
        
        if not mime or mime == "application/octet-stream":
            try:
                import magic
                # Use small chunk
                mime = magic.from_buffer(content[:2048], mime=True)
            except Exception:
                pass
        
        if not mime: return EvidenceType.UNKNOWN
        
        mime = mime.lower()
        if mime.startswith("image/"): return EvidenceType.IMAGE
        if mime.startswith("audio/"): return EvidenceType.AUDIO
        if mime.startswith("video/"): return EvidenceType.VIDEO
        if mime.startswith("application/pdf") or filename.lower().endswith(".pdf"): 
            return EvidenceType.DOCUMENT
        if mime.startswith("text/"): return EvidenceType.DOCUMENT
        
        return EvidenceType.UNKNOWN
