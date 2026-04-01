"""
Seed script to insert initial required data: admin user, schools, branches.
Run once after schema.sql.
"""
import asyncio
from sqlalchemy import select
from core.database import async_session_factory
from core.config import settings

# Since hash_password isn't fully implemented yet, use a fallback
from core.security import hash_password
from models.user import School, Branch, User, UserRole

async def seed_schools(session):
    schools_data = [
        ('se', 'School of Engineering'),
        ('sm', 'School of Management'),
        ('ss', 'School of Sciences')
    ]
    # Admin can add more schools via the admin panel in a future enhancement. For now, seeded here.
    for code, name in schools_data:
        stmt = select(School).filter_by(code=code)
        result = await session.execute(stmt)
        if not result.scalars().first():
            session.add(School(code=code, name=name))

async def seed_branches(session):
    branches_data = [
        ('CSE',  'Computer Science Engineering',       'se'),
        ('ECE',  'Electronics & Communication Eng.',   'se'),
        ('MECH', 'Mechanical Engineering',             'se'),
        ('CIVIL','Civil Engineering',                  'se'),
        ('IT',   'Information Technology',             'se'),
        ('MBA',  'Master of Business Administration',  'sm'),
        ('BBA',  'Bachelor of Business Administration','sm'),
        ('MSC',  'Master of Science',                  'ss'),
        ('BSC',  'Bachelor of Science',                'ss')
    ]
    # Admin can add more branches via admin panel in a future enhancement.
    for bcode, bname, scode in branches_data:
        stmt_branch = select(Branch).filter_by(code=bcode)
        result_branch = await session.execute(stmt_branch)
        if not result_branch.scalars().first():
            # Get school id
            stmt_school = select(School).filter_by(code=scode)
            school = (await session.execute(stmt_school)).scalars().first()
            if school:
                session.add(Branch(code=bcode, name=bname, school_id=school.id))

async def seed_admin(session):
    email = settings.ADMIN_EMAIL
    stmt = select(User).filter_by(email=email)
    result = await session.execute(stmt)
    if not result.scalars().first():
        hp = hash_password(settings.ADMIN_INITIAL_PASSWORD)
        hashed_pw = hp if hp is not None else "temp_hash"
        
        admin = User(
            email=email,
            password_hash=hashed_pw,
            role=UserRole.admin,
            first_name='System',
            last_name='Admin',
            is_active=True,
            force_password_reset=True
        )
        session.add(admin)

async def main():
    async with async_session_factory() as session:
        await seed_schools(session)
        # Flush to ensure schools are recognizable by ID for branches
        await session.flush()
        
        await seed_branches(session)
        await seed_admin(session)
        
        await session.commit()
        print("Seed complete.")
    
    from core.database import engine
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
