from fastapi import APIRouter, Depends
from app.api.deps import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/")
async def get_evidence():
    return {"evidence": []}
