
import sys
import os
import io
import asyncio
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app.services.evidence_processor import EvidenceProcessor, EvidenceType
from app.models.local_models import LocalEvidence
from PIL import Image, ImageDraw

def create_dummy_image(text="CORRUPTION EVIDENCE"):
    """Create a simple image with text for OCR testing."""
    img = Image.new('RGB', (400, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Default font is usually valid
    d.text((10, 40), text, fill=(0, 0, 0))
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def mockup_local_evidence(content, filename):
    """Mock LocalEvidence object."""
    class MockEvidence:
        def __init__(self, c, n):
            self.file_name = n
            self.content_bytes = c
            self.file_path = f"temp_verify_{n}"
            with open(self.file_path, "wb") as f:
                f.write(c)
    return MockEvidence(content, filename)

def cleanup_files(files):
    for f in files:
        if os.path.exists(f):
            os.remove(f)

async def main():
    print("=== STARTING EVIDENCE PROCESSOR VERIFICATION ===")
    
    # Check explicit path
    tess_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tess_path):
        print(f"✅ Found Tesseract at {tess_path}")
    else:
        print(f"⚠️ Tesseract NOT found at {tess_path}. OCR might fail if not in PATH.")

    import shutil
    if not shutil.which("tesseract") and not os.path.exists(tess_path):
        print("⚠️ Tesseract NOT found in PATH. OCR test will verify 'missing dependency' handling.")

    # 1. OCR Test
    print("\n--- Testing OCR (Tesseract) ---")
    img_data = create_dummy_image()
    ev_img = mockup_local_evidence(img_data, "test_ocr.png")
    
    try:
        meta_img = EvidenceProcessor._analyze_single_file(ev_img)
        print(f"File Type Detected: {meta_img.file_type}")
        print(f"OCR Content: '{meta_img.ocr_text_snippet}'")
        
        if "CORRUPTION" in (meta_img.ocr_text_snippet or ""):
             print("✅ OCR SUCCESS: Text extracted correctly.")
        elif meta_img.ocr_text_snippet:
             print("⚠️ OCR PARTIAL: Text extracted but didn't match exactly.")
        else:
             print("❌ OCR FAILED: No text extracted.")
    except Exception as e:
        print(f"❌ OCR CRASH: {e}")

    # Cleanup
    cleanup_files([ev_img.file_path])
    print("\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(main())
