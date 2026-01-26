"""
Test Low Credibility Scoring
Verifies that the enhanced prompt correctly assigns low scores to weak reports.
"""
import asyncio
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.ai import EvidenceMetadata, EvidenceType

async def test_low_credibility_scoring():
    """Test that weak reports get low credibility scores."""
    from app.services.ai_service import GroqService
    
    print("=" * 60)
    print("CREDIBILITY SCORING TEST - Weak Evidence Scenarios")
    print("=" * 60)
    
    # Test Case 1: Vague narrative, NO evidence
    print("\n[TEST 1] Vague narrative + NO evidence")
    print("-" * 40)
    chat_history_1 = [
        {"role": "user", "content": "I saw corruption happening."},
        {"role": "assistant", "content": "Can you tell me more about what happened?"},
        {"role": "user", "content": "Someone took money. That's all I know."}
    ]
    evidence_1 = []  # No evidence
    
    result1, _ = await GroqService.calculate_credibility_score(
        chat_history_1, 
        evidence_1, 
        {"evidence_count": 0, "timestamp": "2026-01-26"},
        timeout=30.0
    )
    
    if result1:
        print(f"  Total Score: {result1.credibility_score}%")
        print(f"  Narrative: {result1.narrative_credibility.score}/40")
        print(f"  Evidence: {result1.evidence_strength.score}/40")
        print(f"  Behavioral: {result1.behavioral_reliability.score}/20")
        print(f"  ✓ PASS" if result1.credibility_score < 40 else f"  ✗ FAIL - Expected <40%")
    else:
        print("  ERROR: No result returned")
    
    # Test Case 2: Some details but UNRELATED evidence
    print("\n[TEST 2] Some details + UNRELATED evidence (cat photo)")
    print("-" * 40)
    chat_history_2 = [
        {"role": "user", "content": "A traffic cop asked me for 500 rupees bribe yesterday at MG Road junction."},
        {"role": "assistant", "content": "Do you have any evidence?"},
        {"role": "user", "content": "Yes I uploaded a photo."}
    ]
    evidence_2 = [
        EvidenceMetadata(
            file_name="cat.jpg",
            file_path="uploads/cat.jpg",
            file_type=EvidenceType.IMAGE,
            is_empty_or_corrupt=False,
            ocr_text_snippet=None,
            object_labels=["sharp_high_clarity_image", "signal: general_scene_or_object"],
            has_relevant_keywords=False
        )
    ]
    
    result2, _ = await GroqService.calculate_credibility_score(
        chat_history_2, 
        evidence_2,
        {"evidence_count": 1, "timestamp": "2026-01-26", "layer1_flags": [e.model_dump() for e in evidence_2]},
        timeout=30.0
    )
    
    if result2:
        print(f"  Total Score: {result2.credibility_score}%")
        print(f"  Narrative: {result2.narrative_credibility.score}/40")
        print(f"  Evidence: {result2.evidence_strength.score}/40")
        print(f"  Behavioral: {result2.behavioral_reliability.score}/20")
        print(f"  ✓ PASS" if result2.credibility_score < 35 else f"  ✗ FAIL - Expected <35%")
    else:
        print("  ERROR: No result returned")
    
    # Test Case 3: Detailed story with BLURRY/CORRUPT evidence
    print("\n[TEST 3] Good narrative + CORRUPT evidence")
    print("-" * 40)
    chat_history_3 = [
        {"role": "user", "content": "On January 15, 2026 at 3pm, Officer Ramesh at the RTO office in Bangalore demanded Rs 2000 for my driving license renewal."},
        {"role": "assistant", "content": "Thank you. Do you have any evidence?"},
        {"role": "user", "content": "Yes, I tried to take a photo but it came out blurry."}
    ]
    evidence_3 = [
        EvidenceMetadata(
            file_name="blurry_photo.jpg",
            file_path="uploads/blurry.jpg",
            file_type=EvidenceType.IMAGE,
            is_empty_or_corrupt=True,
            ocr_text_snippet=None,
            object_labels=["blurry_image", "error: file too large (>5MB)"],
            has_relevant_keywords=False
        )
    ]
    
    result3, _ = await GroqService.calculate_credibility_score(
        chat_history_3, 
        evidence_3,
        {"evidence_count": 1, "timestamp": "2026-01-26", "layer1_flags": [e.model_dump() for e in evidence_3]},
        timeout=30.0
    )
    
    if result3:
        print(f"  Total Score: {result3.credibility_score}%")
        print(f"  Narrative: {result3.narrative_credibility.score}/40")
        print(f"  Evidence: {result3.evidence_strength.score}/40")
        print(f"  Behavioral: {result3.behavioral_reliability.score}/20")
        print(f"  ✓ PASS" if result3.credibility_score < 50 else f"  ✗ FAIL - Expected <50% (good story but bad evidence)")
    else:
        print("  ERROR: No result returned")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_low_credibility_scoring())
