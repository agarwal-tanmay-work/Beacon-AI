from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.models.beacon import Beacon
from app.models.beacon_update import BeaconUpdate
from app.schemas.report import TrackStatusRequest, TrackStatusResponse
from app.core.security import verify_password

router = APIRouter()

@router.post("/track", response_model=TrackStatusResponse)
async def track_case(
    request: TrackStatusRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Track case status using Case ID and Secret Access Key.
    """
    # 1. Fetch Case
    stmt = select(Beacon).where(Beacon.case_id == request.case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    
    # GENERIC ERROR for security (don't reveal if ID exists)
    generic_error = HTTPException(status_code=401, detail="Invalid Case ID or Secret Key")
    
    if not case:
        raise generic_error
        
    # 2. Verify Secret Key
    if not case.secret_key_hash:
        # Legacy cases or error state - cannot strictly track without key
        raise generic_error
        
    if not verify_password(request.secret_key, case.secret_key_hash):
        raise generic_error
        
    # 3. Fetch Latest Public Update
    update_stmt = select(BeaconUpdate).where(BeaconUpdate.case_id == request.case_id).order_by(desc(BeaconUpdate.created_at)).limit(1)
    update_res = await db.execute(update_stmt)
    latest_update = update_res.scalar_one_or_none()
    
    public_msg = latest_update.public_update if latest_update else None
    
    return TrackStatusResponse(
        status=case.status,
        last_updated=case.last_updated_at,
        public_update=public_msg
    )
