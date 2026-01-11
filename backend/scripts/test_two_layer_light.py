
import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# --- MOCK HEAVY MODULES BEFORE IMPORT ---
# This prevents loading cv2/torch which is crashing the shell environment
mock_ev_proc_module = MagicMock()
sys.modules["app.services.evidence_processor"] = mock_ev_proc_module

# Now we can safely import ScoringService
try:
    from app.services.scoring_service import ScoringService
    from app.schemas.ai import EvidenceMetadata, EvidenceType, ScoringResult, NarrativeCredibilityScore, EvidenceStrengthScore, BehavioralReliabilityScore
    print("Imports successful")
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

async def test_scoring_flow():
    print(">>> Starting Lightweight Verification <<<")

    # Mock Data
    mock_chat = [{"role": "user", "content": "I bribed the official."}]
    mock_evidence_objs = [MagicMock(file_path="dummy.jpg")]
    
    mock_flags = [EvidenceMetadata(
        file_name="dummy.jpg", 
        file_type=EvidenceType.IMAGE, 
        is_empty_or_corrupt=False, 
        ocr_text_snippet="Receipt",
        has_relevant_keywords=True
    )]

    mock_score = ScoringResult(
        credibility_score=85,
        narrative_credibility=NarrativeCredibilityScore(score=35, reasoning=["Good"]),
        evidence_strength=EvidenceStrengthScore(score=30, reasoning=["Aligned"]),
        behavioral_reliability=BehavioralReliabilityScore(score=20, reasoning=["Calm"]),
        rationale=["Rational Case"],
        confidence_level="High",
        limitations="None",
        final_safety_statement="Disclaimer"
    )

    # Patch Internal Calls of ScoringService
    with patch('app.services.scoring_service.ScoringService._fetch_chat_history', new_callable=AsyncMock) as mock_fetch_chat:
        mock_fetch_chat.return_value = mock_chat
        
        with patch('app.services.scoring_service.ScoringService._fetch_evidence', new_callable=AsyncMock) as mock_fetch_ev:
            mock_fetch_ev.return_value = mock_evidence_objs
            
            # This mocks the CLASS METHOD on the mocked module we injected
            mock_ev_proc_module.EvidenceProcessor.process_evidence.return_value = mock_flags
                
            with patch('app.services.ai_service.GroqService.generate_pro_summary', new_callable=AsyncMock) as mock_summary:
                mock_summary.return_value = "Summary."
                
                with patch('app.services.ai_service.GroqService.calculate_credibility_score', new_callable=AsyncMock) as mock_calc:
                    mock_calc.return_value = mock_score
                    
                    # Mock DB
                    with patch('app.services.scoring_service.AsyncSessionLocal') as mock_db:
                        session_mock = AsyncMock()
                        mock_db.return_value.__aenter__.return_value = session_mock
                        
                        with patch('app.services.scoring_service.LocalAsyncSession') as mock_local_db:
                            local_session_mock = AsyncMock()
                            mock_local_db.return_value.__aenter__.return_value = local_session_mock
                            
                            # RUN
                            await ScoringService.run_background_scoring("sess_123", "BCN123")
                            
                            # VERIFY
                            if mock_ev_proc_module.EvidenceProcessor.process_evidence.called:
                                print("[PASS] Layer 1 (EvidenceProcessor) Triggered")
                            else:
                                print("[FAIL] Layer 1 NOT Triggered")
                                
                            if mock_calc.called:
                                print("[PASS] Layer 2 (GroqService) Triggered")
                            else:
                                print("[FAIL] Layer 2 NOT Triggered")
                                
                            if session_mock.commit.called:
                                print("[PASS] DB Commit Executed")
                            else:
                                print("[FAIL] DB Commit NOT Executed")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_scoring_flow())
