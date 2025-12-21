import asyncio
import unittest
from unittest.mock import patch, MagicMock
from app.services.ai_service import GroqService
from app.schemas.ai import ScoringResult, ScoringBreakdown

class TestScoringEngine(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        self.mock_chat_history = [
            {"role": "user", "content": "I want to report a bribe."},
            {"role": "assistant", "content": "Can you provide details?"},
            {"role": "user", "content": "The officer at the desk asked for 5000 to process my file."}
        ]
        self.mock_metadata = {"evidence_count": 0, "timestamp": "2025-12-22T03:00:00"}

    @patch("app.services.ai_service.GroqService._call_groq")
    async def test_high_detail_report(self, mock_call):
        # Case 1: High-detail report + strong evidence
        mock_result = ScoringResult(
            credibility_score=85,
            breakdown=ScoringBreakdown(
                information_completeness=20,
                internal_consistency=15,
                evidence_quality=25,
                language_tone=10,
                temporal_proximity=10,
                corroboration_patterns=5,
                user_cooperation=5,
                malicious_penalty=0
            ),
            authority_summary="High-quality report with strong evidence."
        )
        mock_call.return_value = mock_result
        
        result = await GroqService.calculate_scoring_rubric(
            self.mock_chat_history, "Strong video evidence of the bribe.", self.mock_metadata
        )
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["credibility_score"], 75)
        self.assertEqual(result["breakdown"]["evidence_quality"], 25)
        self.assertIn("information_completeness", result["breakdown"])

    @patch("app.services.ai_service.GroqService._call_groq")
    async def test_vague_report(self, mock_call):
        # Case 2: Vague report, no evidence
        mock_result = ScoringResult(
            credibility_score=25,
            breakdown=ScoringBreakdown(
                information_completeness=5,
                internal_consistency=8,
                evidence_quality=0,
                language_tone=5,
                temporal_proximity=3,
                corroboration_patterns=2,
                user_cooperation=2,
                malicious_penalty=0
            ),
            authority_summary="Very vague report lacking key details."
        )
        mock_call.return_value = mock_result
        
        result = await GroqService.calculate_scoring_rubric(
            [{"role": "user", "content": "corruption happened."}], "No evidence.", self.mock_metadata
        )
        
        self.assertLessEqual(result["credibility_score"], 40)
        self.assertEqual(result["breakdown"]["evidence_quality"], 0)

    @patch("app.services.ai_service.GroqService._call_groq")
    async def test_contradictory_narrative(self, mock_call):
        # Case 3: Contradictory narrative
        mock_result = ScoringResult(
            credibility_score=30,
            breakdown=ScoringBreakdown(
                information_completeness=10,
                internal_consistency=3,
                evidence_quality=5,
                language_tone=5,
                temporal_proximity=5,
                corroboration_patterns=2,
                user_cooperation=2,
                malicious_penalty=-2
            ),
            authority_summary="Narrative and evidence don't match."
        )
        mock_call.return_value = mock_result
        
        result = await GroqService.calculate_scoring_rubric(
            self.mock_chat_history, "Weak evidence.", self.mock_metadata
        )
        
        self.assertLessEqual(result["breakdown"]["internal_consistency"], 5)

    @patch("app.services.ai_service.GroqService._call_groq")
    async def test_malicious_penalty(self, mock_call):
        # Case 4: Malicious language / vendetta indicators
        mock_result = ScoringResult(
            credibility_score=20,
            breakdown=ScoringBreakdown(
                information_completeness=10,
                internal_consistency=10,
                evidence_quality=5,
                language_tone=2,
                temporal_proximity=5,
                corroboration_patterns=3,
                user_cooperation=0,
                malicious_penalty=-15
            ),
            authority_summary="Strong indicators of personal vendetta. "
        )
        mock_call.return_value = mock_result
        
        result = await GroqService.calculate_scoring_rubric(
            self.mock_chat_history, "No evidence.", self.mock_metadata
        )
        
        self.assertLessEqual(result["breakdown"]["malicious_penalty"], -10)

    @patch("app.services.ai_service.GroqService._call_groq")
    async def test_clamping_logic(self, mock_call):
        # Test final score clamping [1, 100]
        # We return a dict here to simulate what Llama might return BEFORE validation if we weren't using ge/le
        # But since we use ge/le in ScoringResult, _call_groq would return None for these.
        # To test the MANUAL clamping in calculate_scoring_rubric, we mock return a dict
        # and ensure calculate_scoring_rubric handles it.
        
        mock_data = {
            "credibility_score": 110,
            "breakdown": {
                "information_completeness": 20,
                "internal_consistency": 15,
                "evidence_quality": 25,
                "language_tone": 10,
                "temporal_proximity": 10,
                "corroboration_patterns": 10,
                "user_cooperation": 5,
                "malicious_penalty": 0
            },
            "authority_summary": "Perfect report."
        }
        
        # We need to mock _call_groq such that it returns a MagicMock that behaves like a dict or an object with model_dump
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = mock_data
        mock_call.return_value = mock_obj
        
        result = await GroqService.calculate_scoring_rubric(
            self.mock_chat_history, "No evidence.", self.mock_metadata
        )
        
        self.assertEqual(result["credibility_score"], 100)

        # Scenario: AI returns -5
        mock_data["credibility_score"] = -5
        result = await GroqService.calculate_scoring_rubric(
            self.mock_chat_history, "No evidence.", self.mock_metadata
        )
        
        self.assertEqual(result["credibility_score"], 1)

if __name__ == "__main__":
    unittest.main()
