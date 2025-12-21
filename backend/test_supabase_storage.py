
import asyncio
import uuid
import hashlib
import secrets
from sqlalchemy import select
from app.db.local_db import LocalAsyncSession, init_local_db
from app.models.local_models import LocalSession, LocalConversation, LocalSenderType
from app.db.session import engine
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionType
from sqlalchemy.orm import sessionmaker
from app.models.beacon import Beacon
from app.services.report_engine import ReportEngine
from fastapi import BackgroundTasks

async def test_force_submission():
    # 1. Create a fake session in Local SQLite with unique IDs
    session_id = str(uuid.uuid4()) 
    access_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    
    async with LocalAsyncSession() as local_session:
        new_s = LocalSession(id=session_id, access_token_hash=token_hash)
        local_session.add(new_s)
        
        # Add some messages
        m1 = LocalConversation(session_id=session_id, sender=LocalSenderType.USER, content="I want to report corruption.")
        m2 = LocalConversation(session_id=session_id, sender=LocalSenderType.AI, content="I understand. What happened?")
        local_session.add(m1)
        local_session.add(m2)
        await local_session.commit()
        print(f"Created local session {session_id}")

    # 2. Mock LLMAgent.chat to return a final report
    from unittest.mock import patch
    
    fake_report = {
        "what": "Bribe",
        "where": "City Hall",
        "when": "Today",
        "who": "Inspector",
        "story": "Taking money for permits",
        "evidence": "None"
    }
    
    print(f"Triggering mock submission for {session_id}...")
    with patch("app.services.report_engine.LLMAgent.chat", return_value=("Thank you. Case ID is CASE_ID_PLACEHOLDER", fake_report)):
        LocalSessionMaker = sessionmaker(engine, class_=AsyncSessionType, expire_on_commit=False)
        async with LocalSessionMaker() as sb_session:
            bg_tasks = BackgroundTasks()
            response = await ReportEngine.process_message(
                session_id,
                "Here is my final report.",
                sb_session,
                bg_tasks
            )
            print(f"Response Case ID: {response.case_id}")
            
    # 2b. Manually trigger background scoring to verify UPDATE
    print("Triggering background scoring manually...")
    from app.services.scoring_service import ScoringService
    
    # We need to mock GroqService calls inside calculate_comprehensive_score too
    # to avoid real API calls in this test.
    with patch("app.services.ai_service.GroqService.generate_pro_summary", return_value="Test summary of corruption"):
        with patch("app.services.ai_service.GroqService.extract_credibility_features", return_value={"is_test": True}):
            with patch("app.core.scoring_logic.calculate_deterministically", return_value={"final_score": 85, "justification": "Detailed and consistent test report."}):
                await ScoringService.run_background_scoring(session_id, response.case_id)
            
    # 3. Verify it's in Supabase and UPDATED
    print("Verifying Supabase record...")
    async with LocalSessionMaker() as sb_session:
        stmt = select(Beacon).where(Beacon.case_id == response.case_id)
        result = await sb_session.execute(stmt)
        beacon = result.scalar_one_or_none()
        if beacon:
            print(f"SUCCESS: FOUND in Supabase Beacon table!")
            print(f"   Case ID: {beacon.case_id}")
            print(f"   Summary: {beacon.incident_summary}")
            print(f"   Score: {beacon.credibility_score}")
            print(f"   Explanation: {beacon.score_explanation}")
            if beacon.incident_summary == "Test summary of corruption" and beacon.credibility_score == 85:
                print("SUCCESS: UPDATE VERIFIED!")
            else:
                print("FAILURE: Update did not match expected values")
        else:
            print("FAILURE: NOT FOUND in Supabase Beacon table")

if __name__ == "__main__":
    asyncio.run(test_force_submission())
