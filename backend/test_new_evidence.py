
from app.services.evidence_processor import EvidenceProcessor
from app.models.local_models import LocalEvidence
import json
import os
import structlog

structlog.configure(processors=[structlog.processors.JSONRenderer()])

path = 'C:/Users/priya/.gemini/antigravity/brain/f3097c31-91ff-4164-a5b0-4f0ce40f14e1/uploaded_image_1767965785983.png'

ev = LocalEvidence(
    session_id='test_high_cred',
    file_name='traffic_bribe.png',
    file_path=path
)

if not os.path.exists(path):
    print(f"File not found: {path}")
else:
    meta_list = EvidenceProcessor.process_evidence([ev])
    meta = meta_list[0]
    print("\n" + "="*40)
    print("RELEVANT EVIDENCE ANALYSIS RESULT")
    print("="*40)
    print(f"File Name: {meta.file_name}")
    print(f"Detected Type: {meta.file_type}")
    print(f"OCR Content: {meta.ocr_text_snippet if meta.ocr_text_snippet else '[NO TEXT FOUND]'}")
    print(f"Object Labels: {meta.object_labels}")
    print("="*40)
