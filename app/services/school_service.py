"""
services/school_service.py
Business logic for school and branch management.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models import School, Branch


async def list_schools_with_branches(db: AsyncSession) -> List[School]:
    """
    Returns all schools with their associated branches eagerly loaded.
    """
    stmt = select(School).options(selectinload(School.branches)).order_by(School.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())
