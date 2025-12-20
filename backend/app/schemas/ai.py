from pydantic import BaseModel, Field
from typing import List, Optional

class AIAnalysisResult(BaseModel):
    summary: str = Field(..., description="Concise summary of the report")
    entities: List[str] = Field(default_factory=list, description="Extracted relevant entities (people, places, orgs)")
    detected_language: str = Field(..., description="ISO language code detected")
    corruption_type_confidence: str = Field(..., description="Likely corruption type (e.g. Bribery)")

class AICredibilityScore(BaseModel):
    score: int = Field(..., ge=0, le=100, description="Estimated credibility score 0-100")
    reasoning: str = Field(..., description="Explanation for the score")
