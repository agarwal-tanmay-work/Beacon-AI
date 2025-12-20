from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.report import Report, ReportConversation, ReportStateTracking, SenderType, ReportStatus
from app.schemas.report import MessageResponse
from app.services.llm_agent import LLMAgent
from datetime import datetime
import json
import uuid


class ReportEngine:
    """
    Backend Observer Pattern.
    
    The backend is a PASSIVE OBSERVER. It:
    - Stores messages
    - Forwards to LLM
    - Extracts data silently
    - Generates Case IDs
    - Computes credibility scores
    
    The backend NEVER:
    - Controls conversation flow
    - Forces questions
    - Triggers greetings
    - Overrides LLM responses
    """
    
    @staticmethod
    async def process_message(
        report_id: str,
        user_message: str,
        session: AsyncSession
    ) -> MessageResponse:
        """
        Process a user message:
        1. Store user message
        2. Build conversation history
        3. Forward to LLM (LLM leads)
        4. Store LLM response
        5. Extract fields silently
        6. Handle completion if final report
        """
        
        # 1. Store user message
        user_msg = ReportConversation(
            report_id=report_id,
            sender=SenderType.USER,
            content_redacted=user_message
        )
        session.add(user_msg)
        await session.flush()
        
        # 2. Build conversation history for LLM
        stmt = select(ReportConversation).where(
            ReportConversation.report_id == report_id
        ).order_by(ReportConversation.created_at)
        result = await session.execute(stmt)
        history_objs = result.scalars().all()
        
        # Convert to LLM format: role = "user" | "assistant"
        conversation_history = []
        for msg in history_objs:
            role = "user" if msg.sender == SenderType.USER else "assistant"
            conversation_history.append({
                "role": role,
                "content": msg.content_redacted
            })
        
        # 3. Forward to LLM (LLM is sole conversational authority)
        llm_response, final_report = await LLMAgent.chat(conversation_history)
        
        # 4. Store LLM response
        sys_msg = ReportConversation(
            report_id=report_id,
            sender=SenderType.SYSTEM,
            content_redacted=llm_response
        )
        session.add(sys_msg)
        
        # 5. Silent extraction (internal tracking only)
        # try:
        #     extracted = await LLMAgent.extract_fields(conversation_history)
        #     
        #     # Update state tracking silently
        #     state_stmt = select(ReportStateTracking).where(
        #         ReportStateTracking.report_id == report_id
        #     )
        #     state_res = await session.execute(state_stmt)
        #     state_obj = state_res.scalar_one_or_none()
        #     
        #     if state_obj:
        #         current_data = dict(state_obj.context_data) if state_obj.context_data else {}
        #         current_data["extracted"] = extracted
        #         current_data["last_updated"] = datetime.utcnow().isoformat()
        #         state_obj.context_data = current_data
        #         session.add(state_obj)
        # except Exception as e:
        #     print(f"Extraction error (non-blocking): {e}")
        
        # 6. Handle completion
        next_step = "ACTIVE"
        if final_report:
            next_step = "SUBMITTED"
            
            # Update report
            r_stmt = select(Report).where(Report.id == report_id)
            r_res = await session.execute(r_stmt)
            report = r_res.scalar_one()
            
            report.status = ReportStatus.VERIFIED
            report.case_id = final_report.get("case_id")  # Store the generated case ID
            report.categories = [final_report.get("what", "Corruption Report")]
            report.location_meta = {
                "where": final_report.get("where"),
                "when": final_report.get("when")
            }
            
            # Credibility score (admin only, never shown to user)
            score = final_report.get("credibilityScore", 50)
            if isinstance(score, str):
                try:
                    score = int(score)
                except:
                    score = 50
            report.credibility_score = min(100, max(0, score))
        
        await session.commit()
        
        return MessageResponse(
            report_id=report_id,
            sender=SenderType.SYSTEM,
            content=llm_response,
            timestamp=datetime.utcnow(),
            next_step=next_step
        )

    @staticmethod
    async def initialize_report(report_id: str, session: AsyncSession):
        """
        Initialize a new report.
        
        NO greeting is stored here. The LLM will greet naturally
        when it receives the first user message.
        
        We only set up the state tracking.
        """
        # Initialize state tracking
        state_tracking = ReportStateTracking(
            report_id=report_id,
            current_step="ACTIVE",
            context_data={
                "initialized_at": datetime.utcnow().isoformat(),
                "extracted": {}
            }
        )
        session.add(state_tracking)
        await session.commit()
    
    @staticmethod
    def generate_case_id() -> str:
        """Generate a permanent, immutable Case ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        unique = uuid.uuid4().hex[:8].upper()
        return f"BCN-{timestamp}-{unique}"
