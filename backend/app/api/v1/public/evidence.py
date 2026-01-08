from fastapi import APIRouter

router = APIRouter()

@router.post("/upload")
async def upload_evidence():
    return {"message": "Evidence uploaded (stub)"}
