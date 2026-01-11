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
    # We allow tracking via the visible plain secret_key 
    if not case.secret_key or case.secret_key != request.secret_key:
        # Fallback check against hash if plain mismatch (handles legacy/migration)
        if not case.secret_key_hash or not verify_password(request.secret_key, case.secret_key_hash):
            raise generic_error
        
    # 3. Return Latest Status
    return TrackStatusResponse(
        status=case.status,
        last_updated=case.last_updated_at,
        public_update=case.last_framed_status
    )
