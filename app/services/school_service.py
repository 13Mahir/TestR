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

async def create_school(db: AsyncSession, code: str, name: str) -> School:
    """Creates a new school."""
    # Check if exists
    stmt = select(School).where(School.code == code)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"School with code '{code}' already exists.")
    
    school = School(code=code, name=name)
    db.add(school)
    await db.flush()
    return school

async def create_branch(db: AsyncSession, school_id: int, code: str, name: str) -> Branch:
    """Creates a new branch for a school."""
    # Check if exists for this school
    stmt = select(Branch).where(Branch.school_id == school_id, Branch.code == code)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Branch with code '{code}' already exists for this school.")
    
    branch = Branch(school_id=school_id, code=code, name=name)
    db.add(branch)
    await db.flush()
    return branch
