"""
services/student_service.py
Business logic for student panel: enrolled courses,
dashboard stats, transcript, and exam lobby eligibility.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_, or_, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import ensure_utc
from models import (
    Course, CourseEnrollment, Branch,
    Exam, ExamAttempt, ExamResult, Question,
    AttemptStatus, Answer, MCQOption, QuestionType,
    ProctorViolation,
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
    result = await db.execute(
        select(
            Course,
            Branch.code.label("branch_code"),
            CourseEnrollment.enrolled_at,
        )
        .join(CourseEnrollment,
              CourseEnrollment.course_id == Course.id)
        .join(Branch, Course.branch_id == Branch.id)
        .where(CourseEnrollment.student_id == student_id)
        .order_by(CourseEnrollment.enrolled_at.desc())
    )
    rows = result.all()

    now = datetime.now(timezone.utc)
    courses = []

    for course, branch_code, enrolled_at in rows:
        # Upcoming published exams not yet attempted
        upcoming_r = await db.execute(
            select(func.count(Exam.id))
            .where(
                and_(
                    Exam.course_id    == course.id,
                    Exam.is_published == True,
                    Exam.end_time     > now,
                )
            )
        )
        upcoming = upcoming_r.scalar_one()

        # Completed (attempted) exams
        completed_r = await db.execute(
            select(func.count(ExamAttempt.id))
            .join(Exam, ExamAttempt.exam_id == Exam.id)
            .where(
                and_(
                    Exam.course_id         == course.id,
                    ExamAttempt.student_id == student_id,
                    ExamAttempt.status.in_([
                        AttemptStatus.submitted,
                        AttemptStatus.auto_submitted,
                    ]),
                )
            )
        )
        completed = completed_r.scalar_one()

        courses.append({
            "id":              course.id,
            "course_code":     course.course_code,
            "name":            course.name,
            "description":     course.description,
            "branch_code":     branch_code,
            "year":            course.year,
            "mode":            course.mode.value,
            "is_active":       course.is_active,
            "enrolled_at":     ensure_utc(enrolled_at),
            "upcoming_exams":  upcoming,
            "completed_exams": completed,
        })

    return courses


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
    """
    # Get all enrolled courses
    courses = await get_enrolled_courses(db, student_id)
    output  = []

    for course in courses:
        # Get all published results for this course
        results_r = await db.execute(
            select(ExamResult, Exam)
            .join(Exam, ExamResult.exam_id == Exam.id)
            .where(
                and_(
                    ExamResult.student_id  == student_id,
                    Exam.course_id         == course["id"],
                    Exam.results_published == True,
                    ExamResult.published_at != None,
                )
            )
        )
        rows = results_r.all()

        if not rows:
            continue

        scores     = []
        pass_count = 0
        fail_count = 0

        for er, exam in rows:
            total   = float(exam.total_marks)
            awarded = float(er.total_marks_awarded)
            pct     = (awarded / total * 100) if total > 0 else 0
            scores.append(pct)
            if er.is_pass is True:
                pass_count += 1
            elif er.is_pass is False:
                fail_count += 1

        avg_pct   = sum(scores) / len(scores) if scores else 0
        avg_score = sum(
            float(er.total_marks_awarded) for er, _ in rows
        ) / len(rows)

        output.append({
            "course_code":     course["course_code"],
            "course_name":     course["name"],
            "exams_attempted": len(rows),
            "average_score":   round(avg_score, 2),
            "average_pct":     round(avg_pct, 2),
            "pass_count":      pass_count,
            "fail_count":      fail_count,
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
) -> tuple[Optional[ExamAttempt], Optional[str]]:
    """
    Creates a new ExamAttempt row for the student.

    Validates (re-checks eligibility at creation time):
      - Exam exists and is published.
      - Student is enrolled in the course.
      - No existing attempt for this student+exam.
      - Current time is between start_time and end_time.
        (The lobby allows entry 5 min early but the attempt
         can only be created at or after start_time.)

    Returns:
        (ExamAttempt, None)      on success
        (None, error_string)     on failure

    Does NOT commit — caller commits.
    """
    # Load exam
    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        return None, "Exam not found."
    if not exam.is_published:
        return None, "Exam is not published."

    # Enrollment check
    enrolled = await verify_student_enrolled(
        db, student_id, exam.course_id
    )
    if not enrolled:
        return None, "You are not enrolled in this course."

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
        return None, "You have already attempted this exam."

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
        return None, (
            f"Exam has not started yet. "
            f"Starts in {mins} minute(s)."
        )
    if now > end:
        return None, "The exam window has closed."

    attempt = ExamAttempt(
        exam_id=exam_id,
        student_id=student_id,
        ip_address=ip_address,
        status=AttemptStatus.in_progress,
    )
    db.add(attempt)
    await db.flush()
    await db.refresh(attempt)
    return attempt, None


async def get_exam_questions_for_student(
    db: AsyncSession,
    exam_id: int,
) -> list[dict]:
    """
    Returns questions for an exam attempt — student view.
    is_correct is STRIPPED from all MCQ options so students
    cannot see correct answers via the API.
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
            q_dict["options"] = [
                {
                    "id":           o.id,
                    "option_label": o.option_label,
                    "option_text":  o.option_text,
                    # is_correct intentionally omitted
                }
                for o in opts_r.scalars().all()
            ]
        output.append(q_dict)

    return output


async def save_answer(
    db: AsyncSession,
    attempt_id: int,
    question_id: int,
    selected_option_id: Optional[int] = None,
    subjective_text: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Saves or updates a student's answer for one question.

    Validates:
      - Attempt is still in_progress.
      - Question belongs to the attempt's exam.
      - For MCQ: selected_option_id belongs to question.
      - Only one of selected_option_id or subjective_text
        is provided (based on question type).

    Upserts: creates answer if first save, updates if exists.

    Returns:
        (True, "Answer saved.")
        (False, error_string)

    Does NOT commit — caller commits.
    """
    # Verify attempt is in_progress
    attempt_r = await db.execute(
        select(ExamAttempt).where(ExamAttempt.id == attempt_id)
    )
    attempt = attempt_r.scalar_one_or_none()
    if attempt is None:
        return False, "Attempt not found."
    if attempt.status != AttemptStatus.in_progress:
        return False, "This attempt has already been submitted."

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
        return False, "Question not found in this exam."

    # For MCQ: validate option belongs to question
    if question.question_type == QuestionType.mcq:
        if selected_option_id is None:
            # Saving as unanswered — allowed
            pass
        else:
            opt_r = await db.execute(
                select(MCQOption).where(
                    and_(
                        MCQOption.id          == selected_option_id,
                        MCQOption.question_id == question_id,
                    )
                )
            )
            if opt_r.scalar_one_or_none() is None:
                return False, (
                    "Selected option does not belong to "
                    "this question."
                )

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
    return True, "Answer saved."


async def submit_attempt(
    db: AsyncSession,
    attempt_id: int,
    student_id: int,
    auto_submit: bool = False,
) -> tuple[bool, str]:
    """
    Submits an exam attempt and runs auto-grading for MCQ answers.

    Steps:
      1. Verify attempt belongs to student and is in_progress.
      2. Set status = submitted or auto_submitted.
      3. Set submitted_at = now(UTC).
      4. Auto-grade all MCQ answers (with negative marking).
      5. Compute and store ExamResult.

    Negative marking:
      - Correct MCQ: full marks awarded.
      - Wrong MCQ: -(marks × negative_marking_factor) deducted.
      - Unanswered MCQ: 0 marks.

    After this call the student's result is computed but NOT
    visible until the teacher calls publish-results.

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
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
        return False, "Attempt not found."

    attempt, exam = row

    if attempt.status != AttemptStatus.in_progress:
        return False, "This attempt has already been submitted."

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
    factor = float(exam.negative_marking_factor)

    # Get all MCQ questions for this exam
    mcq_qs_r = await db.execute(
        select(Question).where(
            and_(
                Question.exam_id       == exam.id,
                Question.question_type == QuestionType.mcq,
            )
        )
    )
    mcq_questions = mcq_qs_r.scalars().all()

    total_negative = Decimal("0.00")

    for q in mcq_questions:
        # Find answer for this question
        ans_r = await db.execute(
            select(Answer).where(
                and_(
                    Answer.attempt_id  == attempt_id,
                    Answer.question_id == q.id,
                )
            )
        )
        answer = ans_r.scalar_one_or_none()

        if answer is None or answer.selected_option_id is None:
            # Unanswered — create/update with 0 marks
            if answer is None:
                answer = Answer(
                    attempt_id=attempt_id,
                    question_id=q.id,
                    selected_option_id=None,
                    subjective_text=None,
                    is_correct=None,
                    marks_awarded=Decimal("0.00"),
                )
                db.add(answer)
            else:
                answer.is_correct    = None
                answer.marks_awarded = Decimal("0.00")
                db.add(answer)
            continue

        # Check if selected option is correct
        opt_r = await db.execute(
            select(MCQOption).where(
                MCQOption.id == answer.selected_option_id
            )
        )
        option = opt_r.scalar_one_or_none()

        if option and option.is_correct:
            answer.is_correct    = True
            answer.marks_awarded = q.marks
        else:
            # Wrong answer
            penalty = Decimal(str(factor)) * q.marks
            awarded = max(
                Decimal("0.00"),
                Decimal("0.00") - penalty
            )
            answer.is_correct    = False
            answer.marks_awarded = awarded
            total_negative      += penalty

        db.add(answer)

    await db.flush()

    # ── Compute and store ExamResult ──────────────────────────────
    from services.result_service import compute_exam_result

    # Store negative_marks_deducted before computing
    # (compute_exam_result reads existing row)
    existing_result_r = await db.execute(
        select(ExamResult).where(
            ExamResult.attempt_id == attempt_id
        )
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

    return True, (
        "Exam submitted successfully."
        if not auto_submit
        else "Exam auto-submitted — time expired."
    )


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
