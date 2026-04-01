"""
services/proctor_service.py
Service for retrieving proctoring violations and snapshots.
"""
from typing import List, Dict, Any
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import ProctorViolation, ProctorSnapshot
from core.gcs import generate_signed_url
from core.config import settings

async def get_violations_for_attempt(
    db: AsyncSession, 
    attempt_id: int
) -> List[Dict[str, Any]]:
    """
    Returns all violation events for a specific attempt, chronological.
    """
    stmt = (
        select(ProctorViolation)
        .where(ProctorViolation.attempt_id == attempt_id)
        .order_by(ProctorViolation.occurred_at.asc())
    )
    result = await db.execute(stmt)
    violations = result.scalars().all()
    
    return [
        {
            "id": v.id,
            "type": v.violation_type.value,
            "occurred_at": v.occurred_at.isoformat(),
            "details": v.details
        }
        for v in violations
    ]

async def get_snapshots_for_attempt(
    db: AsyncSession, 
    attempt_id: int
) -> List[Dict[str, Any]]:
    """
    Returns all snapshots for a specific attempt with signed URLs.
    """
    stmt = (
        select(ProctorSnapshot)
        .where(ProctorSnapshot.attempt_id == attempt_id)
        .order_by(ProctorSnapshot.captured_at.asc())
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    
    items = []
    for s in snapshots:
        signed_url = await generate_signed_url(
            bucket=settings.GCS_BUCKET_NAME,
            file_path=s.gcs_path,
            expiry_minutes=60
        )
        items.append({
            "id": s.id,
            "captured_at": s.captured_at.isoformat(),
            "url": signed_url
        })
    
    return items
