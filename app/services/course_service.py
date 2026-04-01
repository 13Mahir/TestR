"""
services/course_service.py
Business logic for course management: creation, listing,
activation/deactivation, student enrollment, teacher assignment.
"""

from typing import Optional
from sqlalchemy import select, func, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Course, CourseEnrollment, CourseAssignment,
    Branch, School, User, StudentProfile,
    UserRole, CourseMode,
)


# ── Course CRUD ───────────────────────────────────────────────────────────────

async def create_course(
    db: AsyncSession,
    course_code: str,
    name: str,
    description: Optional[str],
    branch_code: str,
    year: str,
    mode: str,
    created_by_id: int,
) -> tuple[Optional[Course], Optional[str]]:
    """
    Creates a new course.

    Validates:
      - branch_code exists in branches table
      - course_code is unique

    Returns:
        (Course, None)         on success
        (None, error_string)   on failure

    Does NOT commit — caller commits.
    """
    # Validate branch exists
    branch_result = await db.execute(
        select(Branch).where(Branch.code == branch_code)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        return None, (
            f"Branch code '{branch_code}' does not exist. "
            "Add it first via the branches table."
        )

    # Check course_code uniqueness
    existing = await db.execute(
        select(Course).where(Course.course_code == course_code)
    )
    if existing.scalar_one_or_none() is not None:
        return None, f"Course code '{course_code}' already exists."

    course = Course(
        course_code=course_code,
        name=name,
        description=description,
        branch_id=branch.id,
        year=year,
        mode=CourseMode(mode),
        is_active=True,
        created_by=created_by_id,
    )
    db.add(course)
    await db.flush()
    await db.refresh(course)
    return course, None


async def list_courses(
    db: AsyncSession,
    is_active: Optional[bool] = None,
    branch_code: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    Returns paginated courses with enrollment/assignment counts.

    Each item in the returned list is a dict with all CourseOut fields
    including branch_code (resolved from join) and counts.

    Returns:
        (course_dicts_list, total_count)
    """
    # Base query joining Branch to get branch_code
    base_query = (
        select(
            Course,
            Branch.code.label("branch_code"),
        )
        .join(Branch, Course.branch_id == Branch.id)
    )
    count_query = (
        select(func.count(Course.id))
        .join(Branch, Course.branch_id == Branch.id)
    )

    if is_active is not None:
        base_query  = base_query.where(Course.is_active == is_active)
        count_query = count_query.where(Course.is_active == is_active)

    if branch_code:
        base_query  = base_query.where(
            Branch.code == branch_code.upper()
        )
        count_query = count_query.where(
            Branch.code == branch_code.upper()
        )

    if search:
        pattern = f"%{search}%"
        condition = or_(
            Course.course_code.ilike(pattern),
            Course.name.ilike(pattern),
        )
        base_query  = base_query.where(condition)
        count_query = count_query.where(condition)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    rows_result = await db.execute(
        base_query
        .order_by(Course.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = rows_result.all()

    # Build course dicts with counts
    course_dicts = []
    for row in rows:
        course      = row[0]
        branch_code_val = row[1]

        # Enrollment count
        enroll_result = await db.execute(
            select(func.count(CourseEnrollment.id))
            .where(CourseEnrollment.course_id == course.id)
        )
        enrolled_count = enroll_result.scalar_one()

        # Assignment count
        assign_result = await db.execute(
            select(func.count(CourseAssignment.id))
            .where(CourseAssignment.course_id == course.id)
        )
        assigned_count = assign_result.scalar_one()

        course_dicts.append({
            "id":                course.id,
            "course_code":       course.course_code,
            "name":              course.name,
            "description":       course.description,
            "branch_code":       branch_code_val,
            "year":              course.year,
            "mode":              course.mode.value,
            "is_active":         course.is_active,
            "created_at":        course.created_at,
            "enrolled_students": enrolled_count,
            "assigned_teachers": assigned_count,
        })

    return course_dicts, total


async def get_course_by_id(
    db: AsyncSession,
    course_id: int,
) -> Optional[dict]:
    """
    Returns a single course dict (same shape as list_courses items)
    or None if not found.
    """
    result = await db.execute(
        select(Course, Branch.code.label("branch_code"))
        .join(Branch, Course.branch_id == Branch.id)
        .where(Course.id == course_id)
    )
    row = result.one_or_none()
    if row is None:
        return None

    course         = row[0]
    branch_code    = row[1]

    enroll_result = await db.execute(
        select(func.count(CourseEnrollment.id))
        .where(CourseEnrollment.course_id == course.id)
    )
    assigned_result = await db.execute(
        select(func.count(CourseAssignment.id))
        .where(CourseAssignment.course_id == course.id)
    )

    return {
        "id":                course.id,
        "course_code":       course.course_code,
        "name":              course.name,
        "description":       course.description,
        "branch_code":       branch_code,
        "year":              course.year,
        "mode":              course.mode.value,
        "is_active":         course.is_active,
        "created_at":        course.created_at,
        "enrolled_students": enroll_result.scalar_one(),
        "assigned_teachers": assigned_result.scalar_one(),
    }


async def set_course_active(
    db: AsyncSession,
    course_id: int,
    is_active: bool,
) -> tuple[bool, str]:
    """
    Activates or deactivates a course.

    Returns:
        (True, success_message)   if updated
        (False, error_string)     if course not found or already
                                  in the requested state
    Does NOT commit — caller commits.
    """
    result = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    course = result.scalar_one_or_none()
    if course is None:
        return False, f"Course with id {course_id} not found."

    if course.is_active == is_active:
        state = "active" if is_active else "inactive"
        return False, f"Course is already {state}."

    course.is_active = is_active
    db.add(course)
    await db.flush()

    state = "activated" if is_active else "deactivated"
    return True, f"Course '{course.course_code}' {state} successfully."


# ── Student enrollment ────────────────────────────────────────────────────────

async def enroll_student_single(
    db: AsyncSession,
    course_id: int,
    student_email: str,
    enrolled_by_id: int,
) -> tuple[bool, str]:
    """
    Enrolls a single student into a course by email.

    Validates:
      - Course exists and is active
      - User exists and is a student
      - Not already enrolled

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    # Validate course
    course_result = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    course = course_result.scalar_one_or_none()
    if course is None:
        return False, f"Course {course_id} not found."
    if not course.is_active:
        return False, "Cannot enroll into an inactive course."

    # Validate student
    user_result = await db.execute(
        select(User).where(User.email == student_email)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        return False, f"No user found with email '{student_email}'."
    if user.role != UserRole.student:
        return False, f"'{student_email}' is not a student account."
    if not user.is_active:
        return False, f"Student account '{student_email}' is deactivated."

    # Check duplicate enrollment
    existing = await db.execute(
        select(CourseEnrollment).where(
            and_(
                CourseEnrollment.course_id  == course_id,
                CourseEnrollment.student_id == user.id,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False, f"'{student_email}' is already enrolled."

    enrollment = CourseEnrollment(
        course_id=course_id,
        student_id=user.id,
        enrolled_by=enrolled_by_id,
    )
    db.add(enrollment)
    await db.flush()
    return True, f"Student '{student_email}' enrolled successfully."


async def unenroll_student_single(
    db: AsyncSession,
    course_id: int,
    student_email: str,
) -> tuple[bool, str]:
    """
    Removes a single student from a course by email.

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    # Find user
    user_result = await db.execute(
        select(User).where(User.email == student_email)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        return False, f"No user found with email '{student_email}'."

    # Find enrollment
    enroll_result = await db.execute(
        select(CourseEnrollment).where(
            and_(
                CourseEnrollment.course_id  == course_id,
                CourseEnrollment.student_id == user.id,
            )
        )
    )
    enrollment = enroll_result.scalar_one_or_none()
    if enrollment is None:
        return False, f"'{student_email}' is not enrolled in this course."

    await db.delete(enrollment)
    await db.flush()
    return True, f"Student '{student_email}' unenrolled successfully."


async def enroll_students_bulk(
    db: AsyncSession,
    course_id: int,
    batch_year: str,
    branch_code: str,
    roll_start: int,
    roll_end: int,
    enrolled_by_id: int,
) -> tuple[int, int, int, list[str]]:
    """
    Enrolls all students matching batch+branch+roll range into a course.

    Finds student user accounts by looking up student_profiles where:
      batch_year = batch_year AND branch.code = branch_code
      AND roll_number between roll_start and roll_end (zero-padded)

    Returns:
        (enrolled_count, skipped_count, failed_count, error_list)

    Skipped = already enrolled.
    Does NOT commit — caller commits.
    """
    # Validate course
    course_result = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    course = course_result.scalar_one_or_none()
    if course is None:
        return 0, 0, 1, [f"Course {course_id} not found."]
    if not course.is_active:
        return 0, 0, 1, ["Cannot enroll into an inactive course."]

    # Validate branch
    branch_result = await db.execute(
        select(Branch).where(Branch.code == branch_code)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        return 0, 0, 1, [f"Branch '{branch_code}' not found."]

    # Build roll number strings for the range (zero-padded to 3 digits)
    roll_numbers = [f"{r:03d}" for r in range(roll_start, roll_end + 1)]

    # Fetch matching student profiles
    profiles_result = await db.execute(
        select(StudentProfile)
        .where(
            and_(
                StudentProfile.batch_year == batch_year,
                StudentProfile.branch_id  == branch.id,
                StudentProfile.roll_number.in_(roll_numbers),
            )
        )
    )
    profiles = profiles_result.scalars().all()

    if not profiles:
        return 0, 0, 0, [
            f"No students found for batch {batch_year} "
            f"branch {branch_code} in roll range "
            f"{roll_start:03d}-{roll_end:03d}."
        ]

    # Snapshot identifiers before entering the flush loop.
    # SQLAlchemy expires ORM objects after every flush(), so accessing
    # profile.user_id inside the loop after a flush would silently
    # reuse stale/expired data. Capture what we need upfront.
    profile_pairs = [(p.user_id, p.roll_number) for p in profiles]

    enrolled = 0
    skipped  = 0
    failed   = 0
    errors   = []

    for user_id, roll_number in profile_pairs:
        # Check if user is active
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_active:
            skipped += 1
            continue

        # Check duplicate
        existing = await db.execute(
            select(CourseEnrollment).where(
                and_(
                    CourseEnrollment.course_id  == course_id,
                    CourseEnrollment.student_id == user_id,
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        try:
            enrollment = CourseEnrollment(
                course_id=course_id,
                student_id=user_id,
                enrolled_by=enrolled_by_id,
            )
            db.add(enrollment)
            await db.flush()
            enrolled += 1
        except Exception as e:
            failed += 1
            errors.append(
                f"Roll {roll_number}: {str(e)}"
            )

    return enrolled, skipped, failed, errors


# ── Teacher assignment ────────────────────────────────────────────────────────

async def assign_teacher_single(
    db: AsyncSession,
    course_id: int,
    teacher_email: str,
    assigned_by_id: int,
) -> tuple[bool, str, Optional[int]]:
    """
    Assigns a single teacher to a course by email.

    Validates:
      - Course exists
      - User exists and is a teacher
      - Not already assigned

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    # Validate course
    course_result = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    course = course_result.scalar_one_or_none()
    if course is None:
        return False, f"Course {course_id} not found."

    # Validate teacher
    user_result = await db.execute(
        select(User).where(User.email == teacher_email)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        return False, f"No user found with email '{teacher_email}'.", None
    if user.role != UserRole.teacher:
        return False, f"'{teacher_email}' is not a teacher account.", None
    if not user.is_active:
        return False, f"Teacher account '{teacher_email}' is deactivated.", None

    # Check duplicate assignment
    existing = await db.execute(
        select(CourseAssignment).where(
            and_(
                CourseAssignment.course_id  == course_id,
                CourseAssignment.teacher_id == user.id,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False, f"'{teacher_email}' is already assigned to this course.", None

    assignment = CourseAssignment(
        course_id=course_id,
        teacher_id=user.id,
        assigned_by=assigned_by_id,
    )
    db.add(assignment)
    await db.flush()
    return True, f"Teacher '{teacher_email}' assigned successfully.", user.id


async def unassign_teacher_single(
    db: AsyncSession,
    course_id: int,
    teacher_email: str,
) -> tuple[bool, str]:
    """
    Removes a teacher assignment from a course by email.

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    user_result = await db.execute(
        select(User).where(User.email == teacher_email)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        return False, f"No user found with email '{teacher_email}'."

    assign_result = await db.execute(
        select(CourseAssignment).where(
            and_(
                CourseAssignment.course_id  == course_id,
                CourseAssignment.teacher_id == user.id,
            )
        )
    )
    assignment = assign_result.scalar_one_or_none()
    if assignment is None:
        return False, f"'{teacher_email}' is not assigned to this course."

    await db.delete(assignment)
    await db.flush()
    return True, f"Teacher '{teacher_email}' unassigned successfully."


async def assign_teachers_bulk_csv(
    db: AsyncSession,
    course_id: int,
    csv_bytes: bytes,
    assigned_by_id: int,
) -> tuple[int, int, int, list[str], list[int]]:
    """
    Assigns multiple teachers from a CSV file.

    Expected CSV format (header row required):
        first_name,last_name
        John,Smith
        Jane,Doe

    Constructs teacher email as first.last@clg.ac.in and assigns
    each to the course.

    Returns:
        (assigned_count, skipped_count, failed_count, error_list, assigned_ids)

    Does NOT commit — caller commits.
    """
    import csv
    import io
    from utils.email_validator import build_teacher_email

    # Validate course exists
    course_result = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    if course_result.scalar_one_or_none() is None:
        return 0, 0, 1, [f"Course {course_id} not found."], []

    # Parse CSV
    try:
        text   = csv_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        if reader.fieldnames is None:
            return 0, 0, 1, ["CSV file is empty or has no header row."], []

        fieldnames_lower = [f.strip().lower() for f in reader.fieldnames]
        if "first_name" not in fieldnames_lower or \
           "last_name"  not in fieldnames_lower:
            return 0, 0, 1, [
                "CSV must have columns: first_name, last_name."
            ], []

        rows = list(reader)
    except UnicodeDecodeError:
        return 0, 0, 1, ["CSV file must be UTF-8 encoded."], []
    except Exception as e:
        return 0, 0, 1, [f"Failed to parse CSV: {str(e)}"], []

    if not rows:
        return 0, 0, 0, ["CSV file has no data rows."]

    if len(rows) > 100:
        return 0, 0, 1, [
            "CSV exceeds maximum of 100 teacher rows per upload."
        ], []

    assigned = 0
    skipped  = 0
    failed   = 0
    errors   = []
    assigned_ids = []

    for i, row in enumerate(rows, start=2):
        first = (row.get("first_name") or "").strip()
        last  = (row.get("last_name")  or "").strip()

        if not first or not last:
            failed += 1
            errors.append(
                f"Row {i}: first_name and last_name must not be empty."
            )
            continue

        try:
            email = build_teacher_email(first, last)
        except ValueError as e:
            failed += 1
            errors.append(f"Row {i} ({first} {last}): {str(e)}")
            continue

        ok, msg, t_id = await assign_teacher_single(
            db=db,
            course_id=course_id,
            teacher_email=email,
            assigned_by_id=assigned_by_id,
        )

        if ok:
            assigned += 1
            if t_id: assigned_ids.append(t_id)
        elif "already assigned" in msg:
            skipped += 1
        else:
            failed += 1
            errors.append(f"Row {i} ({email}): {msg}")

    return assigned, skipped, failed, errors, assigned_ids


async def get_course_enrollments(
    db: AsyncSession,
    course_id: int,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    Returns paginated list of students enrolled in a course.
    Each item contains: user_id, email, full_name, enrolled_at.
    """
    count_result = await db.execute(
        select(func.count(CourseEnrollment.id))
        .where(CourseEnrollment.course_id == course_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(CourseEnrollment, User)
        .join(User, CourseEnrollment.student_id == User.id)
        .where(CourseEnrollment.course_id == course_id)
        .order_by(CourseEnrollment.enrolled_at.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    items = []
    for enrollment, user in rows:
        items.append({
            "user_id":     user.id,
            "email":       user.email,
            "full_name":   user.full_name,
            "is_active":   user.is_active,
            "enrolled_at": enrollment.enrolled_at,
        })

    return items, total


async def get_course_assignments(
    db: AsyncSession,
    course_id: int,
) -> list[dict]:
    """
    Returns all teachers assigned to a course.
    Not paginated — a course rarely has more than a handful of teachers.
    Each item: user_id, email, full_name, assigned_at.
    """
    result = await db.execute(
        select(CourseAssignment, User)
        .join(User, CourseAssignment.teacher_id == User.id)
        .where(CourseAssignment.course_id == course_id)
        .order_by(CourseAssignment.assigned_at.asc())
    )
    rows = result.all()

    return [
        {
            "user_id":     user.id,
            "email":       user.email,
            "full_name":   user.full_name,
            "is_active":   user.is_active,
            "assigned_at": assignment.assigned_at,
        }
        for assignment, user in rows
    ]
