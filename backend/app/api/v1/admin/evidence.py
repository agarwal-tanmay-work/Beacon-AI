from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_evidence():
    return {"evidence": []}
