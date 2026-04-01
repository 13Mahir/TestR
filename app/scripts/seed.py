import asyncio
import os
import sys
from datetime import datetime, timedelta

# Ensure we can import from the 'app' directory if run from 'app'
sys.path.append(os.getcwd())

from sqlalchemy import select
from core.database import async_session_factory, engine
from core.config import settings
from core.security import hash_password
from models import *

async def seed_schools(session):
    print("Seeding schools...")
    schools_data = [
        ('se', 'School of Engineering'),
        ('sm', 'School of Management'),
        ('ss', 'School of Sciences')
    ]
    for code, name in schools_data:
        stmt = select(School).filter_by(code=code)
        result = await session.execute(stmt)
        if not result.scalars().first():
            session.add(School(code=code, name=name))
    await session.flush()

async def seed_branches(session):
    print("Seeding branches...")
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
    for bcode, bname, scode in branches_data:
        stmt_branch = select(Branch).filter_by(code=bcode)
        result_branch = await session.execute(stmt_branch)
        if not result_branch.scalars().first():
            stmt_school = select(School).filter_by(code=scode)
            school = (await session.execute(stmt_school)).scalars().first()
            if school:
                session.add(Branch(code=bcode, name=bname, school_id=school.id))
    await session.flush()

async def seed_admin(session):
    print("Seeding admin...")
    email = settings.ADMIN_EMAIL
    stmt = select(User).filter_by(email=email)
    result = await session.execute(stmt)
    if not result.scalars().first():
        hashed_pw = hash_password(settings.ADMIN_INITIAL_PASSWORD)
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
    await session.flush()

async def seed_teachers(session):
    print("Seeding teachers...")
    teachers_data = [
        ('john.doe@clg.ac.in', 'T1Pass123', 'John', 'Doe'),
        ('jane.smith@clg.ac.in', 'T2Pass123', 'Jane', 'Smith'),
        ('robert.brown@clg.ac.in', 'T3Pass123', 'Robert', 'Brown'),
    ]
    for email, pwd, fname, lname in teachers_data:
        stmt = select(User).filter_by(email=email)
        result = await session.execute(stmt)
        if not result.scalars().first():
            hashed_pw = hash_password(pwd)
            teacher = User(
                email=email,
                password_hash=hashed_pw,
                role=UserRole.teacher,
                first_name=fname,
                last_name=lname,
                is_active=True
            )
            session.add(teacher)
    await session.flush()

async def seed_students(session):
    print("Seeding students...")
    # Get CSE branch
    stmt_cse = select(Branch).filter_by(code='CSE')
    cse_branch = (await session.execute(stmt_cse)).scalars().first()
    if not cse_branch:
        return

    students_data = [
        ('24cse240@se.clg.ac.in', 'S1Pass123', 'Alice', 'Wonder', '22', '001'),
        ('24cse241@se.clg.ac.in', 'S2Pass123', 'Bob', 'Builder', '22', '002'),
        ('24cse242@se.clg.ac.in', 'S3Pass123', 'Charlie', 'Chaplin', '22', '003'),
    ]
    for email, pwd, fname, lname, batch, roll in students_data:
        stmt = select(User).filter_by(email=email)
        result = await session.execute(stmt)
        if not result.scalars().first():
            hashed_pw = hash_password(pwd)
            user = User(
                email=email,
                password_hash=hashed_pw,
                role=UserRole.student,
                first_name=fname,
                last_name=lname,
                is_active=True
            )
            session.add(user)
            await session.flush() # To get user.id
            
            profile = StudentProfile(
                user_id=user.id,
                batch_year=batch,
                branch_id=cse_branch.id,
                roll_number=roll
            )
            session.add(profile)
    await session.flush()

async def seed_courses(session):
    print("Seeding courses...")
    # Get Admin user
    stmt_admin = select(User).filter_by(role=UserRole.admin)
    admin_user = (await session.execute(stmt_admin)).scalars().first()
    if not admin_user:
        return

    # Get CSE branch
    stmt_cse = select(Branch).filter_by(code='CSE')
    cse_branch = (await session.execute(stmt_cse)).scalars().first()
    if not cse_branch:
        return

    courses_data = [
        ('22CS101T', 'Data Structures', 'Fundamentals of Data Structures', CourseMode.theory),
        ('22CS101P', 'Data Structures Lab', 'Practical Implementation of Data Structures', CourseMode.practical),
        ('22CS102T', 'Algorithms', 'Introduction to Algorithms', CourseMode.theory),
    ]
    for code, name, desc, mode in courses_data:
        stmt = select(Course).filter_by(course_code=code)
        result = await session.execute(stmt)
        if not result.scalars().first():
            course = Course(
                course_code=code,
                name=name,
                description=desc,
                branch_id=cse_branch.id,
                year='22',
                mode=mode,
                created_by=admin_user.id
            )
            session.add(course)
    await session.flush()

async def seed_assignments(session):
    print("Seeding course assignments...")
    # Get Teacher 1 and Teacher 2
    stmt_t1 = select(User).filter_by(email='john.doe@clg.ac.in')
    t1 = (await session.execute(stmt_t1)).scalars().first()
    
    stmt_t2 = select(User).filter_by(email='jane.smith@clg.ac.in')
    t2 = (await session.execute(stmt_t2)).scalars().first()
    
    # Get Courses
    stmt_c1 = select(Course).filter_by(course_code='22CS101T')
    c1 = (await session.execute(stmt_c1)).scalars().first()
    
    stmt_c2 = select(Course).filter_by(course_code='22CS102T')
    c2 = (await session.execute(stmt_c2)).scalars().first()

    # Get Admin
    stmt_admin = select(User).filter_by(role=UserRole.admin)
    admin_user = (await session.execute(stmt_admin)).scalars().first()

    if t1 and c1 and admin_user:
        stmt = select(CourseAssignment).filter_by(course_id=c1.id, teacher_id=t1.id)
        if not (await session.execute(stmt)).scalars().first():
            session.add(CourseAssignment(course_id=c1.id, teacher_id=t1.id, assigned_by=admin_user.id))
            
    if t2 and c2 and admin_user:
        stmt = select(CourseAssignment).filter_by(course_id=c2.id, teacher_id=t2.id)
        if not (await session.execute(stmt)).scalars().first():
            session.add(CourseAssignment(course_id=c2.id, teacher_id=t2.id, assigned_by=admin_user.id))
    await session.flush()

async def seed_enrollments(session):
    print("Seeding course enrollments...")
    # Get Students
    stmt_s1 = select(User).filter_by(email='24cse240@se.clg.ac.in')
    s1 = (await session.execute(stmt_s1)).scalars().first()
    
    stmt_s2 = select(User).filter_by(email='24cse241@se.clg.ac.in')
    s2 = (await session.execute(stmt_s2)).scalars().first()
    
    # Get Courses
    stmt_c1 = select(Course).filter_by(course_code='22CS101T')
    c1 = (await session.execute(stmt_c1)).scalars().first()
    
    stmt_c2 = select(Course).filter_by(course_code='22CS102T')
    c2 = (await session.execute(stmt_c2)).scalars().first()

    # Get Admin
    stmt_admin = select(User).filter_by(role=UserRole.admin)
    admin_user = (await session.execute(stmt_admin)).scalars().first()

    if s1 and c1 and admin_user:
        stmt = select(CourseEnrollment).filter_by(course_id=c1.id, student_id=s1.id)
        if not (await session.execute(stmt)).scalars().first():
            session.add(CourseEnrollment(course_id=c1.id, student_id=s1.id, enrolled_by=admin_user.id))
            
    if s2 and c1 and admin_user:
        stmt = select(CourseEnrollment).filter_by(course_id=c1.id, student_id=s2.id)
        if not (await session.execute(stmt)).scalars().first():
            session.add(CourseEnrollment(course_id=c1.id, student_id=s2.id, enrolled_by=admin_user.id))
            
    if s1 and c2 and admin_user:
        stmt = select(CourseEnrollment).filter_by(course_id=c2.id, student_id=s1.id)
        if not (await session.execute(stmt)).scalars().first():
            session.add(CourseEnrollment(course_id=c2.id, student_id=s1.id, enrolled_by=admin_user.id))
    await session.flush()

async def seed_exams(session):
    print("Seeding sample exams...")
    # Get Teacher 1
    stmt_t1 = select(User).filter_by(email='john.doe@clg.ac.in')
    t1 = (await session.execute(stmt_t1)).scalars().first()
    
    # Get Course 1
    stmt_c1 = select(Course).filter_by(course_code='22CS101T')
    c1 = (await session.execute(stmt_c1)).scalars().first()

    if t1 and c1:
        stmt = select(Exam).filter_by(course_id=c1.id, title='DS Midterm')
        if not (await session.execute(stmt)).scalars().first():
            exam = Exam(
                course_id=c1.id,
                created_by=t1.id,
                title='DS Midterm',
                description='Midterm examination for Data Structures',
                duration_minutes=60,
                total_marks=20,
                passing_marks=8,
                start_time=datetime.now() + timedelta(days=1),
                end_time=datetime.now() + timedelta(days=1, hours=2),
                is_published=True
            )
            session.add(exam)
            await session.flush()
            
            # Add Questions
            q1 = Question(
                exam_id=exam.id,
                question_text='What is the time complexity of searching in a Hash Table?',
                question_type=QuestionType.mcq,
                marks=2,
                order_index=1
            )
            session.add(q1)
            await session.flush()
            
            options = [
                MCQOption(question_id=q1.id, option_label='A', option_text='O(1)', is_correct=True),
                MCQOption(question_id=q1.id, option_label='B', option_text='O(n)', is_correct=False),
                MCQOption(question_id=q1.id, option_label='C', option_text='O(log n)', is_correct=False),
                MCQOption(question_id=q1.id, option_label='D', option_text='O(n^2)', is_correct=False),
            ]
            session.add_all(options)
            
            q2 = Question(
                exam_id=exam.id,
                question_text='Describe the difference between Stack and Queue.',
                question_type=QuestionType.subjective,
                marks=5,
                order_index=2,
                word_limit=200
            )
            session.add(q2)
    await session.flush()

async def main():
    async with async_session_factory() as session:
        try:
            await seed_schools(session)
            await seed_branches(session)
            await seed_admin(session)
            await seed_teachers(session)
            await seed_students(session)
            await seed_courses(session)
            await seed_assignments(session)
            await seed_enrollments(session)
            await seed_exams(session)
            
            await session.commit()
            print("Seed complete successfully.")
        except Exception as e:
            await session.rollback()
            print(f"Error seeding database: {e}")
            raise e
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
