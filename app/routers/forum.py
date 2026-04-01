"""
Forum panel router for the TestR.
Handles threads, replies, and course discussions.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"router": "forum", "status": "ok"}
