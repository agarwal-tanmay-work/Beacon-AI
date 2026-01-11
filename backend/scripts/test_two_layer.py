
import asyncio
import sys
import os
import structlog
import logging

# Configure Logging to see output
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

from unittest.mock import MagicMock, AsyncMock, patch

async def test_scoring_flow():
    print(">>> Starting Two-Layer Credibility Engine Test <<<", file=sys.stderr)
    
    try:
        from app.services.scoring_service import ScoringService
        from app.schemas.ai import EvidenceMetadata, EvidenceType, ScoringResult, NarrativeCredibilityScore, EvidenceStrengthScore, BehavioralReliabilityScore
        print("[PASS] Imports successful", file=sys.stderr)
    except ImportError as e:
        print(f"[FAIL] Import Error: {e}", file=sys.stderr)
        return

    # Mock Dependencies
    mock_chat = [{"role": "user", "content": "I bribed the official."}]
    mock_evidence = [MagicMock(file_path="dummy.jpg")]
    
    # Mock Layer 1 Output
    mock_flags = [EvidenceMetadata(
        file_name="dummy.jpg", 
        file_type=EvidenceType.IMAGE, 
        is_empty_or_corrupt=False, 
        ocr_text_snippet="Tax Receipt",
        has_relevant_keywords=True
    )]
    
    # Mock Layer 2 Output
    mock_score = ScoringResult(
        credibility_score=85,
        narrative_credibility=NarrativeCredibilityScore(score=35, reasoning=["Good"]),
        evidence_strength=EvidenceStrengthScore(score=30, reasoning=["Aligned"]),
        behavioral_reliability=BehavioralReliabilityScore(score=20, reasoning=["Calm"]),
        rationale=["Rational"],
        confidence_level="High",
        limitations="None",
        final_safety_statement="Disclaimer"
    )

    with patch('app.services.scoring_service.ScoringService._fetch_chat_history', new_callable=AsyncMock) as mock_fetch_chat:
        mock_fetch_chat.return_value = mock_chat
        
        with patch('app.services.scoring_service.ScoringService._fetch_evidence', new_callable=AsyncMock) as mock_fetch_ev:
            mock_fetch_ev.return_value = mock_evidence
            
            with patch('app.services.evidence_processor.EvidenceProcessor.process_evidence') as mock_proc:
                mock_proc.return_value = mock_flags
                
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
                                print(">>> Running ScoringService...", file=sys.stderr)
                                await ScoringService.run_background_scoring("sess_123", "BCN123")
                                
                                # VERIFY
                                if mock_proc.called:
                                    print("[PASS] EvidenceProcessor Called", file=sys.stderr)
                                else:
                                    print("[FAIL] EvidenceProcessor NOT Called", file=sys.stderr)
                                    
                                if session_mock.commit.called:
                                    print("[PASS] COMMIT SUCCESS", file=sys.stderr)
                                else:
                                    print("[FAIL] COMMIT NOT CALLED", file=sys.stderr)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_scoring_flow())
