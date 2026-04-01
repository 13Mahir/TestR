import asyncio
import os
import sys

# Ensure we can import from the 'app' directory if run from 'app'
sys.path.append(os.getcwd())

from sqlalchemy import select
from core.database import async_session_factory, engine
from core.security import hash_password
from models import User, UserRole, StudentProfile, Branch, School

async def main():
    async with async_session_factory() as session:
        try:
            # Create or Get School and Branch for the student
            stmt_school = select(School).filter_by(code='se')
            school = (await session.execute(stmt_school)).scalars().first()
            if not school:
                school = School(code='se', name='School of Engineering')
                session.add(school)
                await session.flush()
                
            stmt_branch = select(Branch).filter_by(code='BCP')
            branch = (await session.execute(stmt_branch)).scalars().first()
            if not branch:
                branch = Branch(code='BCP', name='Bachelors of Computer Programming', school_id=school.id)
                session.add(branch)
                await session.flush()

            # 1. Student
            student_email = '24bcp261@se.clg.ac.in'
            student_pass = 'Student@123'
            stmt = select(User).filter_by(email=student_email)
            student = (await session.execute(stmt)).scalars().first()
            if not student:
                student = User(
                    email=student_email,
                    password_hash=hash_password(student_pass),
                    role=UserRole.student,
                    first_name='Test',
                    last_name='Student',
                    is_active=True
                )
                session.add(student)
                await session.flush()
                
                profile = StudentProfile(
                    user_id=student.id,
                    batch_year='24',
                    branch_id=branch.id,
                    roll_number='261'
                )
                session.add(profile)
                await session.flush()
            else:
                student.password_hash = hash_password(student_pass)
                await session.flush()
            
            # 2. Teacher
            teacher_email = 'fistnamel.lastname@clg.ac.in'
            teacher_pass = 'Teacher@123'
            stmt = select(User).filter_by(email=teacher_email)
            teacher = (await session.execute(stmt)).scalars().first()
            if not teacher:
                teacher = User(
                    email=teacher_email,
                    password_hash=hash_password(teacher_pass),
                    role=UserRole.teacher,
                    first_name='Fistnamel',
                    last_name='Lastname',
                    is_active=True
                )
                session.add(teacher)
                await session.flush()
            else:
                teacher.password_hash = hash_password(teacher_pass)
                await session.flush()
                
            # 3. Admin
            admin_email = 'admin@clg.ac.in'
            admin_pass = 'Admin@123'
            stmt = select(User).filter_by(email=admin_email)
            admin = (await session.execute(stmt)).scalars().first()
            if not admin:
                admin = User(
                    email=admin_email,
                    password_hash=hash_password(admin_pass),
                    role=UserRole.admin,
                    first_name='System',
                    last_name='Admin',
                    is_active=True
                )
                session.add(admin)
                await session.flush()
            else:
                admin.password_hash = hash_password(admin_pass)
                await session.flush()

            await session.commit()
            
            print("========================================")
            print("Test users created/updated successfully:")
            print("========================================")
            print(f"Role    : Student")
            print(f"Email   : {student.email}")
            print(f"Password: {student_pass}")
            print(f"User ID : {student.id}")
            print("----------------------------------------")
            print(f"Role    : Teacher")
            print(f"Email   : {teacher.email}")
            print(f"Password: {teacher_pass}")
            print(f"User ID : {teacher.id}")
            print("----------------------------------------")
            print(f"Role    : Admin")
            print(f"Email   : {admin.email}")
            print(f"Password: {admin_pass}")
            print(f"User ID : {admin.id}")
            print("========================================")

        except Exception as e:
            await session.rollback()
            print(f"Error creating custom test users: {e}")
            raise e
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
