"""
services/student_service.py
Business logic for student panel: enrolled courses,
dashboard stats, transcript, and exam lobby eligibility.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_, or_, case, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import ensure_utc
from core.exceptions import (
    NotFoundException, ForbiddenException, ValidationException, ConflictException
)
from models import (
    Course, CourseEnrollment, Branch,
    Exam, ExamAttempt, ExamResult, Question,
    AttemptStatus, Answer, MCQOption, QuestionType,
    ProctorViolation, SubjectiveGrade,
)


# ── Enrolled courses ──────────────────────────────────────────────

async def get_enrolled_courses(
    db: AsyncSession,
    student_id: int,
) -> list[dict]:
    """
    Returns all courses the student is enrolled in with
    upcoming and completed exam counts.
    """
    now = datetime.now(timezone.utc)
    
    # Subquery for upcoming exams count
    upcoming_sub = (
        select(Exam.course_id, func.count(Exam.id).label("upcoming_count"))
        .where(and_(Exam.is_published == True, Exam.end_time > now))
        .group_by(Exam.course_id)
        .subquery()
    )
    
    # Subquery for completed exams count
    completed_sub = (
        select(Exam.course_id, func.count(ExamAttempt.id).label("completed_count"))
        .join(ExamAttempt, Exam.id == ExamAttempt.exam_id)
        .where(and_(
            ExamAttempt.student_id == student_id,
            ExamAttempt.status.in_([AttemptStatus.submitted, AttemptStatus.auto_submitted])
        ))
        .group_by(Exam.course_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Course,
            Branch.code.label("branch_code"),
            CourseEnrollment.enrolled_at,
            func.coalesce(upcoming_sub.c.upcoming_count, 0).label("upcoming_count"),
            func.coalesce(completed_sub.c.completed_count, 0).label("completed_count")
        )
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .join(Branch, Course.branch_id == Branch.id)
        .outerjoin(upcoming_sub, upcoming_sub.c.course_id == Course.id)
        .outerjoin(completed_sub, completed_sub.c.course_id == Course.id)
        .where(CourseEnrollment.student_id == student_id)
        .order_by(CourseEnrollment.enrolled_at.desc())
    )
    rows = result.all()

    return [
        {
            "id":              row.Course.id,
            "course_code":     row.Course.course_code,
            "name":            row.Course.name,
            "description":     row.Course.description,
            "branch_code":     row.branch_code,
            "year":            row.Course.year,
            "mode":            row.Course.mode.value,
            "is_active":       row.Course.is_active,
            "enrolled_at":     ensure_utc(row.enrolled_at),
            "upcoming_exams":  row.upcoming_count,
            "completed_exams": row.completed_count,
        }
        for row in rows
    ]


async def verify_student_enrolled(
    db: AsyncSession,
    student_id: int,
    course_id: int,
) -> bool:
    """Returns True if student is enrolled in the course."""
    r = await db.execute(
        select(CourseEnrollment).where(
            and_(
                CourseEnrollment.student_id == student_id,
                CourseEnrollment.course_id  == course_id,
            )
        )
    )
    return r.scalar_one_or_none() is not None


# ── Dashboard ─────────────────────────────────────────────────────

async def get_recent_results(
    db: AsyncSession,
    student_id: int,
    limit: int = 5,
) -> list[dict]:
    """
    Returns the most recently published results for a student.
    Only returns results where results_published=True on the exam.
    """
    result = await db.execute(
        select(ExamResult, Exam, Course.course_code)
        .join(Exam, ExamResult.exam_id == Exam.id)
        .join(Course, Exam.course_id == Course.id)
        .where(
            and_(
                ExamResult.student_id    == student_id,
                Exam.results_published   == True,
                ExamResult.published_at  != None,
            )
        )
        .order_by(ExamResult.published_at.desc())
        .limit(limit)
    )
    rows = result.all()

    results = []
    for exam_result, exam, course_code in rows:
        total = float(exam.total_marks)
        awarded = float(exam_result.total_marks_awarded)
        pct = (awarded / total * 100) if total > 0 else 0.0
        results.append({
            "exam_id":               exam.id,
            "exam_title":            exam.title,
            "course_code":           course_code,
            "total_marks_awarded":   awarded,
            "total_marks_available": total,
            "percentage":            round(pct, 2),
            "is_pass":               exam_result.is_pass,
            "results_published_at":  ensure_utc(exam_result.published_at),
        })

    return results


async def get_subject_performance(
    db: AsyncSession,
    student_id: int,
) -> list[dict]:
    """
    Returns per-course performance summary for the student.
    Only includes published results.
    Optimized to use a single aggregation query.
    """
    # Query to get stats per course
    query = (
        select(
            Course.course_code,
            Course.name.label("course_name"),
            func.count(ExamResult.id).label("exams_attempted"),
            func.avg(ExamResult.total_marks_awarded).label("avg_awarded"),
            func.avg(Exam.total_marks).label("avg_total_possible"),
            func.sum(case((ExamResult.is_pass == True, 1), else_=0)).label("pass_count"),
            func.sum(case((ExamResult.is_pass == False, 1), else_=0)).label("fail_count"),
        )
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .join(Exam, Exam.course_id == Course.id)
        .join(ExamResult, and_(ExamResult.exam_id == Exam.id, ExamResult.student_id == student_id))
        .where(
            and_(
                CourseEnrollment.student_id == student_id,
                Exam.results_published      == True,
                ExamResult.published_at     != None,
            )
        )
        .group_by(Course.id, Course.course_code, Course.name)
        .order_by(Course.course_code.asc())
    )

    result = await db.execute(query)
    rows = result.all()

    output = []
    for row in rows:
        # Calculate percentage averages
        # Note: avg_awarded / avg_total_possible * 100
        avg_total = float(row.avg_total_possible or 1)
        avg_awarded = float(row.avg_awarded or 0)
        avg_pct = (avg_awarded / avg_total * 100) if avg_total > 0 else 0

        output.append({
            "course_code":     row.course_code,
            "course_name":     row.course_name,
            "exams_attempted": row.exams_attempted,
            "average_score":   round(avg_awarded, 2),
            "average_pct":     round(avg_pct, 2),
            "pass_count":      int(row.pass_count or 0),
            "fail_count":      int(row.fail_count or 0),
        })

    return output



async def get_upcoming_exams(
    db: AsyncSession,
    student_id: int,
    limit: int = 10,
) -> list[dict]:
    """
    Returns upcoming published exams for enrolled courses
    that the student has not yet attempted.
    """
    now = datetime.now(timezone.utc)

    # Enrolled course IDs
    enrolled_r = await db.execute(
        select(CourseEnrollment.course_id)
        .where(CourseEnrollment.student_id == student_id)
    )
    course_ids = [r[0] for r in enrolled_r.all()]

    if not course_ids:
        return []

    # Already attempted exam IDs
    attempted_r = await db.execute(
        select(ExamAttempt.exam_id)
        .where(ExamAttempt.student_id == student_id)
    )
    attempted_ids = {r[0] for r in attempted_r.all()}

    # Upcoming exams
    exams_r = await db.execute(
        select(Exam, Course.course_code)
        .join(Course, Exam.course_id == Course.id)
        .where(
            and_(
                Exam.course_id.in_(course_ids),
                Exam.is_published == True,
                Exam.end_time     > now,
            )
        )
        .order_by(Exam.start_time.asc())
        .limit(limit)
    )
    rows = exams_r.all()

    return [
        {
            "id":               exam.id,
            "course_id":        exam.course_id,
            "course_code":      course_code,
            "title":            exam.title,
            "duration_minutes": exam.duration_minutes,
            "start_time":       ensure_utc(exam.start_time),
            "end_time":         ensure_utc(exam.end_time),
            "total_marks":      float(exam.total_marks),
            "passing_marks":    float(exam.passing_marks),
            "has_attempted":    exam.id in attempted_ids,
        }
        for exam, course_code in rows
    ]


# ── Transcript ────────────────────────────────────────────────────

async def get_transcript(
    db: AsyncSession,
    student_id: int,
) -> list[dict]:
    """
    Returns the complete academic transcript for the student.
    All published results across all courses, newest first.
    """
    result = await db.execute(
        select(ExamResult, Exam, Course)
        .join(Exam, ExamResult.exam_id == Exam.id)
        .join(Course, Exam.course_id == Course.id)
        .join(ExamAttempt,
              ExamResult.attempt_id == ExamAttempt.id)
        .where(
            and_(
                ExamResult.student_id  == student_id,
                Exam.results_published == True,
            )
        )
        .order_by(ExamResult.published_at.desc())
    )
    rows = result.all()

    entries = []
    for er, exam, course in rows:
        total   = float(exam.total_marks)
        awarded = float(er.total_marks_awarded)
        pct     = (awarded / total * 100) if total > 0 else 0

        # Get submission time
        attempt_r = await db.execute(
            select(ExamAttempt).where(
                ExamAttempt.id == er.attempt_id
            )
        )
        attempt = attempt_r.scalar_one_or_none()

        entries.append({
            "course_code":           course.course_code,
            "course_name":           course.name,
            "exam_title":            exam.title,
            "total_marks_awarded":   awarded,
            "total_marks_available": total,
            "percentage":            round(pct, 2),
            "is_pass":               er.is_pass,
            "submitted_at":          ensure_utc(attempt.submitted_at)
                                     if attempt else None,
            "results_published_at":  ensure_utc(er.published_at),
        })

    return entries


# ── Exam lobby ────────────────────────────────────────────────────

async def check_exam_eligibility(
    db: AsyncSession,
    student_id: int,
    exam_id: int,
) -> dict:
    """
    Checks whether a student can attempt a given exam right now.

    Rules:
      1. Exam must be published.
      2. Student must be enrolled in the course.
      3. Student must not have already attempted this exam.
      4. Current time must be within start_time to end_time.
      5. Student can enter the exam lobby up to 5 minutes
         before start_time (to prepare).

    Returns a dict matching ExamLobbyOut schema.
    can_attempt=True means student may start the exam now.
    """
    # Load exam
    exam_r = await db.execute(
        select(Exam, Course.course_code)
        .join(Course, Exam.course_id == Course.id)
        .where(Exam.id == exam_id)
    )
    row = exam_r.one_or_none()
    if row is None:
        return {
            "exam_id":     exam_id,
            "can_attempt": False,
            "reason":      "Exam not found.",
        }

    exam, course_code = row

    # Question count
    q_count_r = await db.execute(
        select(func.count(Question.id))
        .where(Question.exam_id == exam_id)
    )
    q_count = q_count_r.scalar_one()

    base = {
        "exam_id":               exam.id,
        "title":                 exam.title,
        "course_code":           course_code,
        "duration_minutes":      exam.duration_minutes,
        "total_marks":           float(exam.total_marks),
        "passing_marks":         float(exam.passing_marks),
        "negative_marking_factor":
            float(exam.negative_marking_factor),
        "start_time":            ensure_utc(exam.start_time),
        "end_time":              ensure_utc(exam.end_time),
        "question_count":        q_count,
        "can_attempt":           False,
        "reason":                None,
        "minutes_until_start":   None,
    }

    # Check published
    if not exam.is_published:
        base["reason"] = "This exam has not been published yet."
        return base

    # Check enrollment
    enrolled = await verify_student_enrolled(
        db, student_id, exam.course_id
    )
    if not enrolled:
        base["reason"] = (
            "You are not enrolled in the course for this exam."
        )
        return base

    # Check already attempted
    attempt_r = await db.execute(
        select(ExamAttempt).where(
            and_(
                ExamAttempt.exam_id    == exam_id,
                ExamAttempt.student_id == student_id,
            )
        )
    )
    existing = attempt_r.scalar_one_or_none()
    if existing is not None:
        base["reason"] = (
            "You have already attempted this exam."
            if existing.status in (
                AttemptStatus.submitted,
                AttemptStatus.auto_submitted,
            )
            else "You have an in-progress attempt for this exam."
        )
        return base

    # Time window check
    now = datetime.now(timezone.utc)

    start = exam.start_time
    end   = exam.end_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    if now > end:
        base["reason"] = "The exam window has closed."
        return base

    minutes_until = (start - now).total_seconds() / 60
    base["minutes_until_start"] = round(minutes_until, 1)

    # Allow entry up to 5 minutes before start_time
    if minutes_until > 5:
        base["reason"] = (
            f"Exam starts in {round(minutes_until)} minute(s). "
            "You may enter the lobby 5 minutes before start."
        )
        return base

    # All checks passed
    base["can_attempt"] = True
    base["reason"]      = None
    return base


async def start_exam_attempt(
    db: AsyncSession,
    student_id: int,
    exam_id: int,
    ip_address: str,
) -> ExamAttempt:
    """
    Creates a new ExamAttempt row for the student.
    Raises exceptions on failure.
    """
    # Load exam
    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        raise NotFoundException("Exam not found.")
    if not exam.is_published:
        raise ForbiddenException("Exam is not published.")

    # Enrollment check
    enrolled = await verify_student_enrolled(
        db, student_id, exam.course_id
    )
    if not enrolled:
        raise ForbiddenException("You are not enrolled in this course.")

    # Duplicate attempt check
    existing_r = await db.execute(
        select(ExamAttempt).where(
            and_(
                ExamAttempt.exam_id    == exam_id,
                ExamAttempt.student_id == student_id,
            )
        )
    )
    if existing_r.scalar_one_or_none() is not None:
        raise ConflictException("You have already attempted or started this exam.")

    # Time window check
    now   = datetime.now(timezone.utc)
    start = exam.start_time
    end   = exam.end_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    if now < start:
        mins = round((start - now).total_seconds() / 60, 1)
        raise ForbiddenException(f"Exam has not started yet. Starts in {mins} minute(s).")
    if now > end:
        raise ForbiddenException("The exam window has closed.")

    attempt = ExamAttempt(
        exam_id=exam_id,
        student_id=student_id,
        ip_address=ip_address,
        status=AttemptStatus.in_progress,
    )
    db.add(attempt)
    await db.flush()
    await db.refresh(attempt)
    return attempt


async def get_exam_questions_for_student(
    db: AsyncSession,
    exam_id: int,
) -> list[dict]:
    """
    Returns questions for an exam attempt — student view.
    is_correct is STRIPPED from all MCQ options so students
    cannot see correct answers via the API.
    """
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Question)
        .options(selectinload(Question.options))
        .where(Question.exam_id == exam_id)
        .order_by(Question.order_index.asc(), Question.id.asc())
    )
    questions = result.scalars().all()

    output = []
    for q in questions:
        q_dict = {
            "id":            q.id,
            "question_text": q.question_text,
            "question_type": q.question_type.value,
            "marks":         q.marks,
            "order_index":   q.order_index,
            "word_limit":    q.word_limit,
            "options":       [],
        }
        if q.question_type == QuestionType.mcq:
            # options are already loaded via selectinload
            q_dict["options"] = [
                {
                    "id":           o.id,
                    "option_label": o.option_label,
                    "option_text":  o.option_text,
                    # is_correct intentionally omitted
                }
                for o in sorted(q.options, key=lambda x: x.option_label)
            ]
        output.append(q_dict)

    return output


async def save_answer(
    db: AsyncSession,
    attempt_id: int,
    question_id: int,
    selected_option_id: Optional[int] = None,
    subjective_text: Optional[str] = None,
) -> None:
    """
    Saves or updates a student's answer for one question.
    Raises exceptions on failure.
    """
    # Verify attempt is in_progress
    attempt_r = await db.execute(
        select(ExamAttempt).where(ExamAttempt.id == attempt_id)
    )
    attempt = attempt_r.scalar_one_or_none()
    if attempt is None:
        raise NotFoundException("Attempt not found.")
    if attempt.status != AttemptStatus.in_progress:
        raise ForbiddenException("This attempt has already been submitted.")

    # Verify question belongs to exam
    q_r = await db.execute(
        select(Question).where(
            and_(
                Question.id      == question_id,
                Question.exam_id == attempt.exam_id,
            )
        )
    )
    question = q_r.scalar_one_or_none()
    if question is None:
        raise NotFoundException("Question not found in this exam.")

    # For MCQ: validate option belongs to question
    if question.question_type == QuestionType.mcq and selected_option_id is not None:
        opt_r = await db.execute(
            select(MCQOption).where(
                and_(
                    MCQOption.id          == selected_option_id,
                    MCQOption.question_id == question_id,
                )
            )
        )
        if opt_r.scalar_one_or_none() is None:
            raise ValidationException("Selected option does not belong to this question.")

    # Upsert answer
    existing_r = await db.execute(
        select(Answer).where(
            and_(
                Answer.attempt_id  == attempt_id,
                Answer.question_id == question_id,
            )
        )
    )
    existing = existing_r.scalar_one_or_none()

    if existing:
        existing.selected_option_id = selected_option_id
        existing.subjective_text    = subjective_text
        existing.is_correct         = None
        existing.marks_awarded      = None
        db.add(existing)
    else:
        answer = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_id=selected_option_id,
            subjective_text=subjective_text,
            is_correct=None,
            marks_awarded=None,
        )
        db.add(answer)

    await db.flush()


async def submit_attempt(
    db: AsyncSession,
    attempt_id: int,
    student_id: int,
    auto_submit: bool = False,
) -> None:
    """
    Submits an exam attempt and runs auto-grading for MCQ answers.
    Optimized MCQ grading to fetch options in bulk (fix PRC-01 / MOD-02).
    """
    # Verify ownership
    attempt_r = await db.execute(
        select(ExamAttempt, Exam)
        .join(Exam, ExamAttempt.exam_id == Exam.id)
        .where(
            and_(
                ExamAttempt.id         == attempt_id,
                ExamAttempt.student_id == student_id,
            )
        )
    )
    row = attempt_r.one_or_none()
    if row is None:
        raise NotFoundException("Attempt not found.")

    attempt, exam = row

    if attempt.status != AttemptStatus.in_progress:
        raise ForbiddenException("This attempt has already been submitted.")

    now = datetime.now(timezone.utc)

    # Update attempt status
    attempt.status       = (
        AttemptStatus.auto_submitted
        if auto_submit
        else AttemptStatus.submitted
    )
    attempt.submitted_at = now
    db.add(attempt)
    await db.flush()

    # ── Auto-grade MCQ answers ────────────────────────────────────
    factor = Decimal(str(exam.negative_marking_factor))

    # Get all MCQ questions for this exam
    mcq_qs_r = await db.execute(
        select(Question).where(
            and_(
                Question.exam_id       == exam.id,
                Question.question_type == QuestionType.mcq,
            )
        )
    )
    mcq_questions = {q.id: q for q in mcq_qs_r.scalars().all()}
    
    total_negative = Decimal("0.00")

    if mcq_questions:
        # Get all existing answers for this attempt
        ans_r = await db.execute(
            select(Answer).where(Answer.attempt_id == attempt_id)
        )
        answers = {a.question_id: a for a in ans_r.scalars().all()}

        # Collect selected option IDs for bulk fetch
        selected_option_ids = [
            a.selected_option_id for a in answers.values()
            if a.selected_option_id is not None
        ]

        # Bulk fetch all selected options to see which are correct (FIX N+1)
        options_map = {}
        if selected_option_ids:
            opts_r = await db.execute(
                select(MCQOption).where(MCQOption.id.in_(selected_option_ids))
            )
            options_map = {o.id: o for o in opts_r.scalars().all()}

        # Grade each MCQ question
        for q_id, q in mcq_questions.items():
            answer = answers.get(q_id)
            
            if answer is None or answer.selected_option_id is None:
                # Unanswered
                if answer is None:
                    answer = Answer(attempt_id=attempt_id, question_id=q_id)
                answer.is_correct    = None
                answer.marks_awarded = Decimal("0.00")
                db.add(answer)
                continue

            # Check correctness
            option = options_map.get(answer.selected_option_id)
            if option and option.is_correct:
                answer.is_correct    = True
                answer.marks_awarded = q.marks
            else:
                # Wrong answer
                penalty = factor * q.marks
                answer.is_correct    = False
                answer.marks_awarded = Decimal("0.00")
                total_negative      += penalty
            
            db.add(answer)

        await db.flush()

    # ── Compute and store ExamResult ──────────────────────────────
    from services.result_service import compute_exam_result

    existing_result_r = await db.execute(
        select(ExamResult).where(ExamResult.attempt_id == attempt_id)
    )
    existing_result = existing_result_r.scalar_one_or_none()

    if existing_result:
        existing_result.negative_marks_deducted = total_negative
        db.add(existing_result)
    else:
        new_result = ExamResult(
            attempt_id=attempt_id,
            exam_id=exam.id,
            student_id=student_id,
            mcq_marks_awarded=Decimal("0.00"),
            subjective_marks_awarded=Decimal("0.00"),
            negative_marks_deducted=total_negative,
            total_marks_awarded=Decimal("0.00"),
            is_pass=None,
        )
        db.add(new_result)

    await db.flush()
    await compute_exam_result(db=db, attempt_id=attempt_id)



async def get_attempt_status(
    db: AsyncSession,
    attempt_id: int,
    student_id: int,
) -> Optional[dict]:
    """
    Returns status summary of an in-progress attempt.
    Used by the exam timer to verify submission completed.

    Returns None if attempt not found or does not belong
    to student.
    """
    attempt_r = await db.execute(
        select(ExamAttempt).where(
            and_(
                ExamAttempt.id         == attempt_id,
                ExamAttempt.student_id == student_id,
            )
        )
    )
    attempt = attempt_r.scalar_one_or_none()
    if attempt is None:
        return None

    # Count answered questions
    answered_r = await db.execute(
        select(func.count(Answer.id))
        .where(
            and_(
                Answer.attempt_id          == attempt_id,
                Answer.selected_option_id  != None,
            )
        )
    )
    # Also count subjective answers
    subj_answered_r = await db.execute(
        select(func.count(Answer.id))
        .where(
            and_(
                Answer.attempt_id    == attempt_id,
                Answer.subjective_text != None,
            )
        )
    )

    # Total questions
    total_q_r = await db.execute(
        select(func.count(Question.id))
        .where(Question.exam_id == attempt.exam_id)
    )

    return {
        "attempt_id":      attempt.id,
        "status":          attempt.status.value,
        "started_at":      attempt.started_at,
        "submitted_at":    attempt.submitted_at,
        "answered_mcq":    answered_r.scalar_one(),
        "answered_subj":   subj_answered_r.scalar_one(),
        "total_questions": total_q_r.scalar_one(),
    }


async def log_proctor_violation(
    db: AsyncSession,
    attempt_id: int,
    violation_type: str,
    details: Optional[str] = None,
) -> None:
    """
    Records a proctor violation event for an attempt.
    Called from the proctor violation API endpoint.
    Never raises — errors swallowed silently.
    Does NOT commit — caller commits.
    """
    from models import ProctorViolation
    try:
        violation = ProctorViolation(
            attempt_id=attempt_id,
            violation_type=violation_type,
            details=details,
        )
        db.add(violation)
        await db.flush()
    except Exception:
        pass
