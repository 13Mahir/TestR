"""
services/exam_service.py
Business logic for exam lifecycle management:
  - Assigned course listing for teachers
  - Exam CRUD (create, read, update, delete)
  - Question management (MCQ + subjective)
  - Exam publishing
  - total_marks recomputation

Auto-grading, manual grading, and result publishing
are implemented in Prompt 16 (result_service.py).
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import ensure_utc
from models import (
    Course, CourseAssignment, CourseEnrollment,
    Branch, Exam, Question, MCQOption,
    QuestionType, CourseMode, User,
)


# ── Assigned courses ──────────────────────────────────────────────

async def get_assigned_courses(
    db: AsyncSession,
    teacher_id: int,
) -> list[dict]:
    """
    Returns all courses assigned to the given teacher,
    including enrollment count and branch code.

    Returns a list of dicts (not ORM objects) for easy
    serialisation.
    """
    result = await db.execute(
        select(
            Course,
            Branch.code.label("branch_code"),
            CourseAssignment.assigned_at,
        )
        .join(
            CourseAssignment,
            CourseAssignment.course_id == Course.id
        )
        .join(Branch, Course.branch_id == Branch.id)
        .where(CourseAssignment.teacher_id == teacher_id)
        .order_by(CourseAssignment.assigned_at.desc())
    )
    rows = result.all()

    courses = []
    for course, branch_code, assigned_at in rows:
        # Enrollment count
        enroll_r = await db.execute(
            select(func.count(CourseEnrollment.id))
            .where(CourseEnrollment.course_id == course.id)
        )
        enrolled = enroll_r.scalar_one()

        courses.append({
            "id":                course.id,
            "course_code":       course.course_code,
            "name":              course.name,
            "description":       course.description,
            "branch_code":       branch_code,
            "year":              course.year,
            "mode":              course.mode.value,
            "is_active":         course.is_active,
            "enrolled_students": enrolled,
            "assigned_at":       assigned_at,
        })

    return courses


async def verify_teacher_owns_course(
    db: AsyncSession,
    teacher_id: int,
    course_id: int,
) -> bool:
    """
    Returns True if the teacher is assigned to the given course.
    Used as an ownership check before exam operations.
    """
    result = await db.execute(
        select(CourseAssignment).where(
            and_(
                CourseAssignment.teacher_id == teacher_id,
                CourseAssignment.course_id  == course_id,
            )
        )
    )
    return result.scalar_one_or_none() is not None


# ── Exam CRUD ─────────────────────────────────────────────────────

async def create_exam(
    db: AsyncSession,
    course_id: int,
    teacher_id: int,
    title: str,
    description: Optional[str],
    duration_minutes: int,
    negative_marking_factor: float,
    passing_marks: float,
    start_time: datetime,
    end_time: datetime,
) -> tuple[Optional[Exam], Optional[str]]:
    """
    Creates a new exam for a course.

    Validates:
      - Teacher is assigned to the course.
      - Course exists and is active.
      - No other exam for this course overlaps the time window.

    total_marks starts at 0.00 and is recomputed as questions
    are added via _recompute_total_marks().

    Returns:
        (Exam, None)         on success
        (None, error_string) on failure

    Does NOT commit — caller commits.
    """
    # Verify teacher owns course
    owns = await verify_teacher_owns_course(
        db, teacher_id, course_id
    )
    if not owns:
        return None, (
            "You are not assigned to this course and cannot "
            "create exams for it."
        )

    # Verify course exists and is active
    course_r = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    course = course_r.scalar_one_or_none()
    if course is None:
        return None, f"Course {course_id} not found."
    if not course.is_active:
        return None, "Cannot create exams for an inactive course."

    # Check for overlapping exams on the same course
    overlap_r = await db.execute(
        select(Exam).where(
            and_(
                Exam.course_id == course_id,
                Exam.start_time < end_time,
                Exam.end_time   > start_time,
            )
        )
    )
    overlap = overlap_r.scalars().first()
    if overlap is not None:
        return None, (
            f"Exam '{overlap.title}' already exists for this "
            f"course in the time window "
            f"{overlap.start_time} – {overlap.end_time}. "
            "Please choose a non-overlapping time window."
        )

    exam = Exam(
        course_id=course_id,
        created_by=teacher_id,
        title=title,
        description=description,
        duration_minutes=duration_minutes,
        negative_marking_factor=Decimal(
            str(negative_marking_factor)
        ),
        total_marks=Decimal("0.00"),
        passing_marks=Decimal(str(passing_marks)),
        start_time=start_time,
        end_time=end_time,
        is_published=False,
        results_published=False,
    )
    db.add(exam)
    await db.flush()
    await db.refresh(exam)
    return exam, None


async def get_exam_by_id(
    db: AsyncSession,
    exam_id: int,
) -> Optional[dict]:
    """
    Returns a single exam as a dict with course_code and
    question_count, or None if not found.
    """
    result = await db.execute(
        select(Exam, Course.course_code)
        .join(Course, Exam.course_id == Course.id)
        .where(Exam.id == exam_id)
    )
    row = result.one_or_none()
    if row is None:
        return None

    exam, course_code = row

    q_count_r = await db.execute(
        select(func.count(Question.id))
        .where(Question.exam_id == exam_id)
    )
    q_count = q_count_r.scalar_one()

    return _exam_to_dict(exam, course_code, q_count)


async def list_exams_for_teacher(
    db: AsyncSession,
    teacher_id: int,
    course_id: Optional[int] = None,
    is_published: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    Returns paginated exams created by the teacher.
    Optionally filtered by course_id and published state.

    Returns:
        (exam_dicts, total_count)
    """
    base_q = (
        select(Exam, Course.course_code)
        .join(Course, Exam.course_id == Course.id)
        .where(Exam.created_by == teacher_id)
    )
    count_q = (
        select(func.count(Exam.id))
        .where(Exam.created_by == teacher_id)
    )

    if course_id is not None:
        base_q  = base_q.where(Exam.course_id == course_id)
        count_q = count_q.where(Exam.course_id == course_id)

    if is_published is not None:
        base_q  = base_q.where(
            Exam.is_published == is_published
        )
        count_q = count_q.where(
            Exam.is_published == is_published
        )

    total_r = await db.execute(count_q)
    total   = total_r.scalar_one()

    rows_r = await db.execute(
        base_q
        .order_by(Exam.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = rows_r.all()

    exams = []
    for exam, course_code in rows:
        q_count_r = await db.execute(
            select(func.count(Question.id))
            .where(Question.exam_id == exam.id)
        )
        exams.append(
            _exam_to_dict(exam, course_code, q_count_r.scalar_one())
        )

    return exams, total


async def update_exam(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
    **kwargs,
) -> tuple[bool, str]:
    """
    Updates mutable fields of an exam.
    An exam that has been published (is_published=True) cannot
    be updated — teacher must unpublish first (not supported
    in this system — once published it is final).

    Only non-None values in kwargs are applied.

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        return False, f"Exam {exam_id} not found."

    if exam.created_by != teacher_id:
        return False, "You can only edit your own exams."

    if exam.is_published:
        return False, (
            "This exam has already been published and cannot "
            "be edited."
        )

    allowed = {
        "title", "description", "duration_minutes",
        "negative_marking_factor", "passing_marks",
        "start_time", "end_time",
    }
    
    # Check for overlaps if times are changing
    new_start = kwargs.get("start_time", exam.start_time)
    new_end   = kwargs.get("end_time",   exam.end_time)
    
    if "start_time" in kwargs or "end_time" in kwargs:
        overlap_r = await db.execute(
            select(Exam).where(
                and_(
                    Exam.course_id == exam.course_id,
                    Exam.id != exam.id, # Exclude self
                    Exam.start_time < new_end,
                    Exam.end_time   > new_start,
                )
            )
        )
        overlap = overlap_r.scalars().first()
        if overlap is not None:
            return False, (
                f"Cannot update times: overlaps with exam "
                f"'{overlap.title}' ({overlap.start_time} – "
                f"{overlap.end_time})."
            )

    for field, value in kwargs.items():
        if field in allowed and value is not None:
            if field == "negative_marking_factor":
                value = Decimal(str(value))
            if field == "passing_marks":
                value = Decimal(str(value))
            setattr(exam, field, value)

    db.add(exam)
    await db.flush()
    return True, "Exam updated successfully."


async def delete_exam(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
) -> tuple[bool, str]:
    """
    Deletes an exam. Only allowed if the exam has not been
    published and has no student attempts.

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    from models import ExamAttempt

    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        return False, f"Exam {exam_id} not found."

    if exam.created_by != teacher_id:
        return False, "You can only delete your own exams."

    if exam.is_published:
        return False, (
            "Cannot delete a published exam. "
            "Published exams are permanent."
        )

    # Check for any attempts
    attempt_r = await db.execute(
        select(func.count(ExamAttempt.id))
        .where(ExamAttempt.exam_id == exam_id)
    )
    attempt_count = attempt_r.scalar_one()
    if attempt_count > 0:
        return False, (
            f"Cannot delete exam with {attempt_count} "
            "existing student attempt(s)."
        )

    await db.delete(exam)
    await db.flush()
    return True, "Exam deleted successfully."


async def publish_exam(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
) -> tuple[bool, str]:
    """
    Publishes an exam making it visible to enrolled students.

    Pre-publish validation:
      - Exam must have at least 1 question.
      - Exam must not already be published.
      - start_time must be in the future.
      - passing_marks must be <= total_marks.

    On success:
      - Sets is_published = True and published_at = now(UTC).

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        return False, f"Exam {exam_id} not found."

    if exam.created_by != teacher_id:
        return False, "You can only publish your own exams."

    if exam.is_published:
        return False, "Exam is already published."

    # Check question count
    q_count_r = await db.execute(
        select(func.count(Question.id))
        .where(Question.exam_id == exam_id)
    )
    q_count = q_count_r.scalar_one()
    if q_count == 0:
        return False, (
            "Cannot publish an exam with no questions. "
            "Add at least one question first."
        )

    # Check start_time is in the future (with 1 min grace period)
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    start = exam.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    
    if start < (now - timedelta(minutes=1)):
        return False, (
            "Cannot publish an exam whose start time has "
            "already passed. Update the start time first."
        )

    # Check passing_marks <= total_marks
    if exam.passing_marks > exam.total_marks:
        return False, (
            f"passing_marks ({exam.passing_marks}) exceeds "
            f"total_marks ({exam.total_marks}). "
            "Update passing_marks before publishing."
        )

    exam.is_published = True
    exam.published_at = datetime.now(timezone.utc)
    db.add(exam)
    await db.flush()
    return True, "Exam published successfully."


# ── Question management ───────────────────────────────────────────

async def verify_teacher_owns_exam(
    db: AsyncSession,
    teacher_id: int,
    exam_id: int,
) -> Optional[Exam]:
    """
    Returns the Exam if the teacher created it, else None.
    Used as ownership check before question operations.
    """
    result = await db.execute(
        select(Exam).where(
            and_(
                Exam.id         == exam_id,
                Exam.created_by == teacher_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def add_mcq_question(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
    question_text: str,
    marks: float,
    order_index: int,
    options: list[dict],
) -> tuple[Optional[Question], Optional[str]]:
    """
    Adds an MCQ question to an exam.

    Validates:
      - Teacher owns exam.
      - Exam is not yet published.
      - Exactly one option is marked correct.
      - No duplicate option labels.

    On success: recomputes exam.total_marks.

    Returns:
        (Question, None)         on success
        (None, error_string)     on failure

    Does NOT commit — caller commits.
    """
    exam = await verify_teacher_owns_exam(
        db, teacher_id, exam_id
    )
    if exam is None:
        return None, (
            "Exam not found or you do not own this exam."
        )
    if exam.is_published:
        return None, (
            "Cannot add questions to a published exam."
        )

    question = Question(
        exam_id=exam_id,
        question_text=question_text,
        question_type=QuestionType.mcq,
        marks=Decimal(str(marks)),
        order_index=order_index,
        word_limit=None,
    )
    db.add(question)
    await db.flush()

    for opt in options:
        mcq_opt = MCQOption(
            question_id=question.id,
            option_label=opt["option_label"],
            option_text=opt["option_text"],
            is_correct=opt["is_correct"],
        )
        db.add(mcq_opt)

    await db.flush()

    # Recompute exam total_marks
    await _recompute_total_marks(db, exam_id)

    return question, None


async def add_subjective_question(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
    question_text: str,
    marks: float,
    order_index: int,
    word_limit: Optional[int],
) -> tuple[Optional[Question], Optional[str]]:
    """
    Adds a subjective question to an exam.

    Validates:
      - Teacher owns exam.
      - Exam is not yet published.

    On success: recomputes exam.total_marks.

    Returns:
        (Question, None)         on success
        (None, error_string)     on failure

    Does NOT commit — caller commits.
    """
    exam = await verify_teacher_owns_exam(
        db, teacher_id, exam_id
    )
    if exam is None:
        return None, (
            "Exam not found or you do not own this exam."
        )
    if exam.is_published:
        return None, (
            "Cannot add questions to a published exam."
        )

    question = Question(
        exam_id=exam_id,
        question_text=question_text,
        question_type=QuestionType.subjective,
        marks=Decimal(str(marks)),
        order_index=order_index,
        word_limit=word_limit,
    )
    db.add(question)
    await db.flush()

    # Recompute exam total_marks
    await _recompute_total_marks(db, exam_id)

    return question, None


async def get_exam_questions(
    db: AsyncSession,
    exam_id: int,
) -> list[dict]:
    """
    Returns all questions for an exam ordered by order_index.
    Each question dict includes options for MCQ questions.

    Used by: teacher exam builder, student exam attempt.
    For students: is_correct is stripped in the router layer.
    """
    result = await db.execute(
        select(Question)
        .where(Question.exam_id == exam_id)
        .order_by(Question.order_index.asc(), Question.id.asc())
    )
    questions = result.scalars().all()

    output = []
    for q in questions:
        q_dict = {
            "id":            q.id,
            "exam_id":       q.exam_id,
            "question_text": q.question_text,
            "question_type": q.question_type.value,
            "marks":         float(q.marks),
            "order_index":   q.order_index,
            "word_limit":    q.word_limit,
            "options":       [],
        }

        if q.question_type == QuestionType.mcq:
            opts_r = await db.execute(
                select(MCQOption)
                .where(MCQOption.question_id == q.id)
                .order_by(MCQOption.option_label.asc())
            )
            opts = opts_r.scalars().all()
            q_dict["options"] = [
                {
                    "id":           o.id,
                    "option_label": o.option_label,
                    "option_text":  o.option_text,
                    "is_correct":   o.is_correct,
                }
                for o in opts
            ]

        output.append(q_dict)

    return output


async def delete_question(
    db: AsyncSession,
    question_id: int,
    teacher_id: int,
) -> tuple[bool, str]:
    """
    Deletes a question from an exam.
    Only allowed if the exam is not yet published.
    Recomputes total_marks after deletion.

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    # Find question
    q_r = await db.execute(
        select(Question).where(Question.id == question_id)
    )
    question = q_r.scalar_one_or_none()
    if question is None:
        return False, f"Question {question_id} not found."

    # Verify teacher owns the exam
    exam = await verify_teacher_owns_exam(
        db, teacher_id, question.exam_id
    )
    if exam is None:
        return False, (
            "Exam not found or you do not own this exam."
        )
    if exam.is_published:
        return False, (
            "Cannot delete questions from a published exam."
        )

    exam_id = question.exam_id
    await db.delete(question)
    await db.flush()

    # Recompute total_marks
    await _recompute_total_marks(db, exam_id)

    return True, "Question deleted successfully."


# ── Internal helpers ──────────────────────────────────────────────

async def _recompute_total_marks(
    db: AsyncSession,
    exam_id: int,
) -> None:
    """
    Recomputes and updates exam.total_marks as the sum of
    all question marks for this exam.

    Called automatically after every question add/delete.
    Does NOT commit — caller commits.
    """
    total_r = await db.execute(
        select(func.sum(Question.marks))
        .where(Question.exam_id == exam_id)
    )
    total = total_r.scalar_one() or Decimal("0.00")

    await db.execute(
        update(Exam)
        .where(Exam.id == exam_id)
        .values(total_marks=total)
    )
    await db.flush()


def _exam_to_dict(
    exam: Exam,
    course_code: str,
    question_count: int,
) -> dict:
    """
    Converts an Exam ORM object to a serialisable dict.
    Shared by get_exam_by_id and list_exams_for_teacher.
    """
    return {
        "id":                      exam.id,
        "course_id":               exam.course_id,
        "course_code":             course_code,
        "title":                   exam.title,
        "description":             exam.description,
        "duration_minutes":        exam.duration_minutes,
        "negative_marking_factor": float(
            exam.negative_marking_factor
        ),
        "total_marks":             float(exam.total_marks),
        "passing_marks":           float(exam.passing_marks),
        "start_time":              ensure_utc(exam.start_time),
        "end_time":                ensure_utc(exam.end_time),
        "is_published":            exam.is_published,
        "results_published":       exam.results_published,
        "published_at":            ensure_utc(exam.published_at),
        "results_published_at":    ensure_utc(exam.results_published_at),
        "question_count":          question_count,
        "created_at":              ensure_utc(exam.created_at),
        "updated_at":              ensure_utc(exam.updated_at),
    }
