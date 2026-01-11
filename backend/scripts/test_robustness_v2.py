import asyncio
import os
import sys
import structlog
from unittest.mock import MagicMock
from app.services.evidence_processor import EvidenceProcessor
from app.schemas.ai import EvidenceType

# Configure structlog for the test
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)

async def run_verification():
    print(">>> BEACON ROBUSTNESS VERIFICATION v2 <<<")
    
    # Setup test files
    test_dir = "test_files_robustness"
    os.makedirs(test_dir, exist_ok=True)
    
    files = {
        "normal.txt": b"This is a normal evidence file.",
        "duplicate.txt": b"This is a normal evidence file.",
        "large.bin": b"0" * (6 * 1024 * 1024), # 6MB
        "test.pdf": b"%PDF-1.4...", # Mock PDF header
        "test.mp4": b"ftypmp42..."  # Mock Video header
    }
    
    for name, content in files.items():
        with open(os.path.join(test_dir, name), "wb") as f:
            f.write(content)
            
    # Mock LocalEvidence objects
    evidence_objs = [
        MagicMock(file_name="normal.txt", file_path=os.path.abspath(os.path.join(test_dir, "normal.txt"))),
        MagicMock(file_name="duplicate.txt", file_path=os.path.abspath(os.path.join(test_dir, "duplicate.txt"))),
        MagicMock(file_name="large.bin", file_path=os.path.abspath(os.path.join(test_dir, "large.bin"))),
        MagicMock(file_name="test.pdf", file_path=os.path.abspath(os.path.join(test_dir, "test.pdf"))),
        MagicMock(file_name="test.mp4", file_path=os.path.abspath(os.path.join(test_dir, "test.mp4"))),
    ]
    
    print("\n--- Running Processor ---")
    results = EvidenceProcessor.process_evidence(evidence_objs)
    
    for res in results:
        print(f"\nFile: {res.file_name}")
        print(f"  Type: {res.file_type}")
        print(f"  Size: {res.file_size or 'N/A'} bytes")
        print(f"  Hash: {res.file_hash or 'N/A'}")
        print(f"  Duplicate: {res.is_duplicate}")
        print(f"  Empty/Corrupt: {res.is_empty_or_corrupt}")
        if res.object_labels:
            print(f"  Labels: {res.object_labels}")

    # Specific Checks
    print("\n--- Summary Verification ---")
    
    # 1. Duplicate Check
    if results[1].is_duplicate:
        print("✅ Duplicate Detection: SUCCESS")
    else:
        print("❌ Duplicate Detection: FAILED")
        
    # 2. Size Limit Check
    if results[2].is_empty_or_corrupt and any("too large" in str(l) for l in results[2].object_labels):
        print("✅ Size Limit (5MB): SUCCESS")
    else:
        print("❌ Size Limit (5MB): FAILED")

    # Cleanup
    for name in files:
        file_p = os.path.join(test_dir, name)
        if os.path.exists(file_p):
            os.remove(file_p)
    os.rmdir(test_dir)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_verification())
