import asyncio
import os
import sys

# Mocking parts of the app to test Scoring logic
sys.path.append(os.getcwd())

from app.services.ai_service import GroqService
from app.schemas.ai import EvidenceMetadata, EvidenceType

async def test_unrelated_evidence():
    print("Testing Unrelated Evidence Scoring...")
    
    chat_history = [
        {"role": "user", "content": "I want to report a high-level bribe in the infrastructure department. A contractor paid $50,000 to the head of the department to secure a bridge contract."},
        {"role": "assistant", "content": "Thank you for the report. Do you have any evidence?"},
        {"role": "user", "content": "Yes, I am uploading a photo now."},
    ]
    
    # Evidence is a photo of a cat (unrelated)
    evidence_metadata = [
        EvidenceMetadata(
            file_name="cute_cat.jpg",
            file_path="supastorage://evidence/cute_cat.jpg",
            file_type=EvidenceType.IMAGE,
            object_labels=["sharp_high_clarity_image", "signal: possible_animal_in_scene"]
        )
    ]
    
    metadata_context = {
        "evidence_count": 1,
        "timestamp": "2026-01-21T18:00:00Z",
        "layer1_flags": [m.model_dump() for m in evidence_metadata]
    }
    
    score_result, _ = await GroqService.calculate_credibility_score(chat_history, evidence_metadata, metadata_context)
    
    if score_result:
        print(f"\nCredibility Score: {score_result.credibility_score}")
        print(f"Evidence Strength Score: {score_result.evidence_strength.score}")
        print(f"Rationale: {score_result.rationale}")
        
        if score_result.evidence_strength.score <= 10:
            print("\nSUCCESS: AI correctly identified unrelated evidence and gave a low score.")
        else:
            print("\nFAILURE: AI gave too high a score for unrelated evidence.")
    else:
        print("\nERROR: No score result returned.")

async def test_related_evidence():
    print("\nTesting Related Evidence Scoring...")
    
    chat_history = [
        {"role": "user", "content": "I am reporting a police officer taking cash for a traffic violation."},
        {"role": "assistant", "content": "Can you provide any photo of the incident?"},
        {"role": "user", "content": "Yes, I have a photo of the officer holding cash."},
    ]
    
    # Evidence is related (currency colors detected)
    evidence_metadata = [
        EvidenceMetadata(
            file_name="bribe.jpg",
            file_path="supastorage://evidence/bribe.jpg",
            file_type=EvidenceType.IMAGE,
            object_labels=["sharp_high_clarity_image", "signal: possible_currency_colors"]
        )
    ]
    
    metadata_context = {
        "evidence_count": 1,
        "timestamp": "2026-01-21T18:00:00Z",
        "layer1_flags": [m.model_dump() for m in evidence_metadata]
    }
    
    score_result, _ = await GroqService.calculate_credibility_score(chat_history, evidence_metadata, metadata_context)
    
    if score_result:
        print(f"\nCredibility Score: {score_result.credibility_score}")
        print(f"Evidence Strength Score: {score_result.evidence_strength.score}")
        print(f"Rationale: {score_result.rationale}")
        
        if score_result.evidence_strength.score >= 20:
            print("\nSUCCESS: AI correctly identified related evidence and gave a decent score.")
        else:
            print("\nFAILURE: AI gave too low a score for related evidence.")
    else:
        print("\nERROR: No score result returned.")

if __name__ == "__main__":
    asyncio.run(test_unrelated_evidence())
    asyncio.run(test_related_evidence())
