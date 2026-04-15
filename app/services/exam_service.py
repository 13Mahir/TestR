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
from core.exceptions import (
    NotFoundException, ForbiddenException, ValidationException, ConflictException
)


# ── Assigned courses ──────────────────────────────────────────────

async def get_assigned_courses(
    db: AsyncSession,
    teacher_id: int,
) -> list[dict]:
    """
    Returns all courses assigned to the given teacher,
    including enrollment count and branch code.
    """
    result = await db.execute(
        select(
            Course,
            Branch.code.label("branch_code"),
            CourseAssignment.assigned_at,
            func.count(CourseEnrollment.id).label("enrolled_count")
        )
        .join(CourseAssignment, CourseAssignment.course_id == Course.id)
        .join(Branch, Course.branch_id == Branch.id)
        .outerjoin(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .where(CourseAssignment.teacher_id == teacher_id)
        .group_by(Course.id, Branch.code, CourseAssignment.assigned_at)
        .order_by(CourseAssignment.assigned_at.desc())
    )
    rows = result.all()

    return [
        {
            "id":                row.Course.id,
            "course_code":       row.Course.course_code,
            "name":              row.Course.name,
            "description":       row.Course.description,
            "branch_code":       row.branch_code,
            "year":              row.Course.year,
            "mode":              row.Course.mode.value,
            "is_active":         row.Course.is_active,
            "enrolled_students": row.enrolled_count,
            "assigned_at":       row.assigned_at,
        }
        for row in rows
    ]


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
    negative_marking_factor: Decimal,
    passing_marks: Decimal,
    start_time: datetime,
    end_time: datetime,
) -> Exam:
    """
    Creates a new exam for a course.
    Raises exceptions on failure.
    """
    # Verify teacher owns course
    owns = await verify_teacher_owns_course(
        db, teacher_id, course_id
    )
    if not owns:
        raise ForbiddenException("You are not assigned to this course and cannot create exams for it.")

    # Verify course exists and is active
    course_r = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    course = course_r.scalar_one_or_none()
    if course is None:
        raise NotFoundException(f"Course {course_id} not found.")
    if not course.is_active:
        raise ForbiddenException("Cannot create exams for an inactive course.")

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
        raise ConflictException(
            f"Exam '{overlap.title}' already exists for this course in the time window "
            f"{overlap.start_time} – {overlap.end_time}."
        )

    exam = Exam(
        course_id=course_id,
        created_by=teacher_id,
        title=title,
        description=description,
        duration_minutes=duration_minutes,
        negative_marking_factor=negative_marking_factor,
        total_marks=Decimal("0.00"),
        passing_marks=passing_marks,
        start_time=start_time,
        end_time=end_time,
        is_published=False,
        results_published=False,
    )
    db.add(exam)
    await db.flush()
    await db.refresh(exam)
    return exam


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
    """
    base_q = (
        select(
            Exam,
            Course.course_code,
            func.count(Question.id).label("question_count")
        )
        .join(Course, Exam.course_id == Course.id)
        .outerjoin(Question, Question.exam_id == Exam.id)
        .where(Exam.created_by == teacher_id)
        .group_by(Exam.id, Course.course_code)
    )
    
    count_q = (
        select(func.count(Exam.id))
        .where(Exam.created_by == teacher_id)
    )

    if course_id is not None:
        base_q  = base_q.where(Exam.course_id == course_id)
        count_q = count_q.where(Exam.course_id == course_id)

    if is_published is not None:
        base_q  = base_q.where(Exam.is_published == is_published)
        count_q = count_q.where(Exam.is_published == is_published)

    total_r = await db.execute(count_q)
    total   = total_r.scalar_one()

    rows_r = await db.execute(
        base_q
        .order_by(Exam.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = rows_r.all()

    exams = [
        _exam_to_dict(row.Exam, row.course_code, row.question_count)
        for row in rows
    ]

    return exams, total


async def update_exam(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
    **kwargs,
) -> None:
    """
    Updates mutable fields of an exam.
    An exam that has been published (is_published=True) cannot be updated.
    Raises exceptions on failure.
    """
    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        raise NotFoundException(f"Exam {exam_id} not found.")

    if exam.created_by != teacher_id:
        raise ForbiddenException("You can only edit your own exams.")

    if exam.is_published:
        raise ValidationException("This exam has already been published and cannot be edited.")

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
            raise ConflictException(
                f"Cannot update times: overlaps with exam '{overlap.title}' "
                f"({overlap.start_time} – {overlap.end_time})."
            )

    for field, value in kwargs.items():
        if field in allowed and value is not None:
            setattr(exam, field, value)

    db.add(exam)
    await db.flush()


async def delete_exam(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
) -> None:
    """
    Deletes an exam. Only allowed if the exam has not been published and has no student attempts.
    Raises exceptions on failure.
    """
    from models import ExamAttempt

    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        raise NotFoundException(f"Exam {exam_id} not found.")

    if exam.created_by != teacher_id:
        raise ForbiddenException("You can only delete your own exams.")

    if exam.is_published:
        raise ValidationException("Cannot delete a published exam. Published exams are permanent.")

    # Check for any attempts
    attempt_r = await db.execute(
        select(func.count(ExamAttempt.id))
        .where(ExamAttempt.exam_id == exam_id)
    )
    attempt_count = attempt_r.scalar_one()
    if attempt_count > 0:
        raise ConflictException(f"Cannot delete exam with {attempt_count} existing student attempt(s).")

    await db.delete(exam)
    await db.flush()


async def publish_exam(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
) -> None:
    """
    Publishes an exam.
    Raises exceptions on failure.
    """
    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        raise NotFoundException(f"Exam {exam_id} not found.")

    if exam.created_by != teacher_id:
        raise ForbiddenException("You can only publish your own exams.")

    if exam.is_published:
        raise ConflictException("Exam is already published.")

    # Check question count
    q_count_r = await db.execute(
        select(func.count(Question.id))
        .where(Question.exam_id == exam_id)
    )
    q_count = q_count_r.scalar_one()
    if q_count == 0:
        raise ValidationException("Cannot publish an exam with no questions. Add at least one question first.")

    # Check start_time is in the future
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    start = exam.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    
    if start < (now - timedelta(minutes=1)):
        raise ValidationException("Cannot publish an exam whose start time has already passed. Update the start time first.")

    # Check passing_marks <= total_marks
    if exam.passing_marks > exam.total_marks:
        raise ValidationException(
            f"passing_marks ({exam.passing_marks}) exceeds total_marks ({exam.total_marks}). "
            "Update passing_marks before publishing."
        )

    exam.is_published = True
    exam.published_at = datetime.now(timezone.utc)
    db.add(exam)
    await db.flush()


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
    marks: Decimal,
    order_index: int,
    options: list[dict],
) -> Question:
    """
    Adds an MCQ question to an exam.
    Raises exceptions on failure.
    """
    exam = await verify_teacher_owns_exam(
        db, teacher_id, exam_id
    )
    if exam is None:
        raise NotFoundException(f"Exam {exam_id} not found or you do not own this exam.")
    if exam.is_published:
        raise ValidationException("Cannot add questions to a published exam.")

    question = Question(
        exam_id=exam_id,
        question_text=question_text,
        question_type=QuestionType.mcq,
        marks=marks,
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

    return question


async def add_subjective_question(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
    question_text: str,
    marks: Decimal,
    order_index: int,
    word_limit: Optional[int],
) -> Question:
    """
    Adds a subjective question to an exam.
    Raises exceptions on failure.
    """
    exam = await verify_teacher_owns_exam(
        db, teacher_id, exam_id
    )
    if exam is None:
        raise NotFoundException(f"Exam {exam_id} not found or you do not own this exam.")
    if exam.is_published:
        raise ValidationException("Cannot add questions to a published exam.")

    question = Question(
        exam_id=exam_id,
        question_text=question_text,
        question_type=QuestionType.subjective,
        marks=marks,
        order_index=order_index,
        word_limit=word_limit,
    )
    db.add(question)
    await db.flush()

    # Recompute exam total_marks
    await _recompute_total_marks(db, exam_id)

    return question


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
            "marks":         q.marks,
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
) -> None:
    """
    Deletes a question from an exam.
    Only allowed if the exam is not yet published.
    Raises exceptions on failure.
    """
    # Find question
    q_r = await db.execute(
        select(Question).where(Question.id == question_id)
    )
    question = q_r.scalar_one_or_none()
    if question is None:
        raise NotFoundException(f"Question {question_id} not found.")

    # Verify teacher owns the exam
    exam = await verify_teacher_owns_exam(
        db, teacher_id, question.exam_id
    )
    if exam is None:
        raise ForbiddenException("Exam not found or you do not own this exam.")
    if exam.is_published:
        raise ValidationException("Cannot delete questions from a published exam.")

    exam_id = question.exam_id
    await db.delete(question)
    await db.flush()

    # Recompute exam total_marks
    await _recompute_total_marks(db, exam_id)


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
        "negative_marking_factor": exam.negative_marking_factor,
        "total_marks":             exam.total_marks,
        "passing_marks":           exam.passing_marks,
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
