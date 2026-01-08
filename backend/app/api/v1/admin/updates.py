from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.beacon import Beacon
from app.models.beacon_update import BeaconUpdate
from app.schemas.report import NGOUpdateRequest, NGOUpdateResponse
from app.services.llm_agent import LLMAgent
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/{id}/update", response_model=NGOUpdateResponse)
async def update_case_status(
    id: uuid.UUID,
    request: NGOUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    NGO submits an internal update.
    LLM rewrites it for public display.
    """
    # 1. Fetch Case
    case = await db.get(Beacon, id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    # 2. Rewrite Update via LLM
    public_text = await LLMAgent.rewrite_update(request.raw_update)
    
    # 3. Create Update Record
    update_record = BeaconUpdate(
        case_id=case.case_id,
        raw_update=request.raw_update,
        public_update=public_text,
        updated_by=request.updated_by
    )
    db.add(update_record)
    
    # 4. Update Main Case Status
    # Simple logic: If update contains "closed" or "resolved", mark resolved? 
    # For now, just keep status as generic "In Progress" or update if provided manually.
    # But requirement said DO NOT allow editing past updates.
    # Let's update the last_updated_at
    case.last_updated_at = datetime.utcnow()
    # We could infer status from text or let it be passed. Plan didn't specify strict status transitions.
    # We will assume status remains current unless manually changed, but update timestamp.
    
    await db.commit()
    await db.refresh(update_record)
    
    return NGOUpdateResponse(
        status=case.status,
        public_update=public_text,
        timestamp=case.last_updated_at
    )
