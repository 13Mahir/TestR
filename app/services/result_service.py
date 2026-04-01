"""
services/result_service.py
Business logic for the exam grading and result lifecycle:
  - Fetching student attempts + answers for teacher review
  - Auto-grading MCQ answers (called on exam submit)
  - Submitting subjective grades by teacher
  - Computing and storing exam results
  - Publishing results (making them visible to students)
  - Grade book generation
  - CSV and PDF export of grade book

Auto-grading on submit is triggered from the student attempt
endpoint (Prompt 20). This file provides the grading helpers
that both the student submit endpoint and the teacher grading
endpoint call.
"""

import csv
import io
import json
from datetime import datetime, timezone
from core.utils import ensure_utc
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Exam, Question, MCQOption, QuestionType,
    ExamAttempt, Answer, SubjectiveGrade, ExamResult,
    CourseEnrollment, User, AttemptStatus, ProctorViolation,
)


# ── Attempt listing for teacher ───────────────────────────────────

async def get_exam_attempts_for_grading(
    db: AsyncSession,
    exam_id: int,
) -> list[dict]:
    """
    Returns a list of all student attempt summaries for an exam.
    Used by the teacher grading list view.

    For each enrolled student, returns their attempt status,
    current marks totals, grading completion state,
    and violation count.

    Students who never started the exam are included
    with status='not_attempted'.
    """
    # Get all enrolled students for this exam's course
    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        return []

    enrolled_r = await db.execute(
        select(CourseEnrollment, User)
        .join(User, CourseEnrollment.student_id == User.id)
        .where(CourseEnrollment.course_id == exam.course_id)
        .order_by(User.email.asc())
    )
    enrolled_rows = enrolled_r.all()

    # Pre-fetch violation summaries for all attempts of this exam to avoid N+1 queries
    viols_r = await db.execute(
        select(
            ProctorViolation.attempt_id,
            ProctorViolation.violation_type,
            func.count(ProctorViolation.id)
        )
        .join(ExamAttempt, ProctorViolation.attempt_id == ExamAttempt.id)
        .where(ExamAttempt.exam_id == exam_id)
        .group_by(ProctorViolation.attempt_id, ProctorViolation.violation_type)
    )
    # viol_map: { attempt_id -> { "tab_switch": 2, ... } }
    viol_map = {}
    for aid, vtype, vcount in viols_r.all():
        if aid not in viol_map:
            viol_map[aid] = {}
        # violation_type is an Enum, use .value for the string key
        viol_map[aid][vtype.value] = vcount

    summaries = []
    for enrollment, user in enrolled_rows:
        # Find attempt
        attempt_r = await db.execute(
            select(ExamAttempt).where(
                and_(
                    ExamAttempt.exam_id    == exam_id,
                    ExamAttempt.student_id == user.id,
                )
            )
        )
        attempt = attempt_r.scalar_one_or_none()

        if attempt is None:
            summaries.append({
                "attempt_id":          None,
                "student_id":          user.id,
                "student_email":       user.email,
                "student_name":        user.full_name,
                "started_at":          None,
                "submitted_at":        None,
                "status":              "not_attempted",
                "mcq_marks":           0.0,
                "subjective_marks":    0.0,
                "total_marks_awarded": 0.0,
                "is_fully_graded":     False,
                "violation_count":     0,
                "violation_summary":   {},
            })
            continue

        # MCQ marks from auto-graded answers
        mcq_r = await db.execute(
            select(func.coalesce(
                func.sum(Answer.marks_awarded), 0
            ))
            .join(Question, Answer.question_id == Question.id)
            .where(
                and_(
                    Answer.attempt_id    == attempt.id,
                    Question.question_type == QuestionType.mcq,
                    Answer.marks_awarded  != None,
                )
            )
        )
        mcq_marks = float(mcq_r.scalar_one() or 0)

        # Subjective marks from teacher grades
        subj_r = await db.execute(
            select(func.coalesce(
                func.sum(SubjectiveGrade.marks_awarded), 0
            ))
            .join(Answer,
                  SubjectiveGrade.answer_id == Answer.id)
            .where(Answer.attempt_id == attempt.id)
        )
        subj_marks = float(subj_r.scalar_one() or 0)

        # Check if all subjective questions are graded
        subj_q_count_r = await db.execute(
            select(func.count(Question.id))
            .where(
                and_(
                    Question.exam_id == exam_id,
                    Question.question_type == QuestionType.subjective,
                )
            )
        )
        subj_q_count = subj_q_count_r.scalar_one()

        graded_count_r = await db.execute(
            select(func.count(SubjectiveGrade.id))
            .join(Answer,
                  SubjectiveGrade.answer_id == Answer.id)
            .where(Answer.attempt_id == attempt.id)
        )
        graded_count = graded_count_r.scalar_one()

        is_fully_graded = (
            subj_q_count == 0 or
            graded_count >= subj_q_count
        )

        # Violation info from pre-fetched map
        v_summary = viol_map.get(attempt.id, {})
        v_total = sum(v_summary.values())

        summaries.append({
            "attempt_id":          attempt.id,
            "student_id":          user.id,
            "student_email":       user.email,
            "student_name":        user.full_name,
            "started_at":          ensure_utc(attempt.started_at),
            "submitted_at":        ensure_utc(attempt.submitted_at),
            "status":              attempt.status.value,
            "mcq_marks":           mcq_marks,
            "subjective_marks":    subj_marks,
            "total_marks_awarded": mcq_marks + subj_marks,
            "is_fully_graded":     is_fully_graded,
            "violation_count":     v_total,
            "violation_summary":   v_summary,
        })

    return summaries


async def get_student_answers_for_grading(
    db: AsyncSession,
    attempt_id: int,
) -> list[dict]:
    """
    Returns all answers for a student's attempt,
    enriched with question text, correct option info
    (for MCQ), and existing grade (for subjective).

    Used by the teacher per-student grading detail view.
    """
    answers_r = await db.execute(
        select(Answer, Question)
        .join(Question, Answer.question_id == Question.id)
        .where(Answer.attempt_id == attempt_id)
        .order_by(Question.order_index.asc(), Question.id.asc())
    )
    rows = answers_r.all()

    output = []
    for answer, question in rows:
        entry = {
            "answer_id":          answer.id,
            "question_id":        question.id,
            "question_text":      question.question_text,
            "question_type":      question.question_type.value,
            "marks_available":    float(question.marks),
            "word_limit":         question.word_limit,
            "selected_option_id": answer.selected_option_id,
            "selected_label":     None,
            "selected_text":      None,
            "correct_label":      None,
            "is_correct":         answer.is_correct,
            "subjective_text":    answer.subjective_text,
            "marks_awarded":      float(answer.marks_awarded)
                                  if answer.marks_awarded is not None
                                  else None,
            "teacher_feedback":   None,
            "is_graded":          False,
        }

        if question.question_type == QuestionType.mcq:
            # Fetch all options to get labels and correct answer
            opts_r = await db.execute(
                select(MCQOption)
                .where(
                    MCQOption.question_id == question.id
                )
            )
            opts = opts_r.scalars().all()
            opt_map = {o.id: o for o in opts}

            # Selected option label + text
            if answer.selected_option_id is not None:
                sel = opt_map.get(answer.selected_option_id)
                if sel:
                    entry["selected_label"] = sel.option_label
                    entry["selected_text"]  = sel.option_text

            # Correct option label
            correct = next(
                (o for o in opts if o.is_correct), None
            )
            if correct:
                entry["correct_label"] = correct.option_label

        elif question.question_type == QuestionType.subjective:
            # Fetch existing grade if any
            grade_r = await db.execute(
                select(SubjectiveGrade)
                .where(
                    SubjectiveGrade.answer_id == answer.id
                )
            )
            grade = grade_r.scalar_one_or_none()
            if grade:
                entry["marks_awarded"]   = float(
                    grade.marks_awarded
                )
                entry["teacher_feedback"] = grade.feedback
                entry["is_graded"]        = True

        output.append(entry)

    return output


# ── Subjective grading ────────────────────────────────────────────

async def grade_subjective_answer(
    db: AsyncSession,
    answer_id: int,
    teacher_id: int,
    marks_awarded: float,
    feedback: Optional[str],
) -> tuple[bool, str]:
    """
    Submits or updates a teacher's grade for a subjective answer.

    Validates:
      - Answer exists and belongs to a subjective question.
      - marks_awarded does not exceed the question's marks.
      - The exam the answer belongs to is published
        (cannot grade unpublished exam attempts).

    Creates a SubjectiveGrade row if first time grading,
    or updates the existing row.

    Also updates answers.marks_awarded to match so result
    computation has a single source.

    Returns:
        (True, success_message)
        (False, error_string)

    Does NOT commit — caller commits.
    """
    # Load answer + question + attempt + exam
    answer_r = await db.execute(
        select(Answer, Question, ExamAttempt, Exam)
        .join(Question, Answer.question_id == Question.id)
        .join(ExamAttempt, Answer.attempt_id == ExamAttempt.id)
        .join(Exam, ExamAttempt.exam_id == Exam.id)
        .where(Answer.id == answer_id)
    )
    row = answer_r.one_or_none()
    if row is None:
        return False, f"Answer {answer_id} not found."

    answer, question, attempt, exam = row

    # Must be subjective
    if question.question_type != QuestionType.subjective:
        return False, (
            "Only subjective answers can be manually graded. "
            "MCQ answers are auto-graded."
        )

    # marks_awarded must not exceed question marks
    if Decimal(str(marks_awarded)) > question.marks:
        return False, (
            f"marks_awarded ({marks_awarded}) cannot exceed "
            f"the question's available marks "
            f"({float(question.marks)})."
        )

    # Exam must be published (students can only attempt
    # published exams, so this is a safeguard)
    if not exam.is_published:
        return False, "Exam is not published."

    # Upsert SubjectiveGrade
    existing_r = await db.execute(
        select(SubjectiveGrade)
        .where(SubjectiveGrade.answer_id == answer_id)
    )
    existing = existing_r.scalar_one_or_none()

    if existing:
        existing.marks_awarded = Decimal(str(marks_awarded))
        existing.feedback      = feedback
        existing.graded_by     = teacher_id
        existing.graded_at     = ensure_utc(datetime.now(timezone.utc))
        db.add(existing)
    else:
        grade = SubjectiveGrade(
            answer_id=answer_id,
            graded_by=teacher_id,
            marks_awarded=Decimal(str(marks_awarded)),
            feedback=feedback,
        )
        db.add(grade)

    # Update answers.marks_awarded to match
    answer.marks_awarded = Decimal(str(marks_awarded))
    db.add(answer)

    await db.flush()
    return True, (
        f"Grade saved: {marks_awarded} / {float(question.marks)}"
    )


# ── Result computation ────────────────────────────────────────────

async def compute_exam_result(
    db: AsyncSession,
    attempt_id: int,
) -> Optional[dict]:
    """
    Computes and upserts the exam_results row for an attempt.

    Calculation:
      mcq_marks    = sum of answers.marks_awarded
                     for MCQ questions (includes negative marking
                     already applied at answer time)
      subj_marks   = sum of subjective_grades.marks_awarded
      negative     = stored separately (computed at submit time
                     in student attempt endpoint, Prompt 20)
      total        = mcq_marks + subj_marks

    Note: negative_marks_deducted is written at auto-grade time
    (student submit). This function reads what is already stored.

    Returns the result dict, or None on failure.
    Does NOT commit — caller commits.
    """
    attempt_r = await db.execute(
        select(ExamAttempt, Exam)
        .join(Exam, ExamAttempt.exam_id == Exam.id)
        .where(ExamAttempt.id == attempt_id)
    )
    row = attempt_r.one_or_none()
    if row is None:
        return None

    attempt, exam = row

    # MCQ marks (auto-graded; marks_awarded already accounts
    # for negative marking from the student submit step)
    mcq_r = await db.execute(
        select(func.coalesce(func.sum(Answer.marks_awarded), 0))
        .join(Question, Answer.question_id == Question.id)
        .where(
            and_(
                Answer.attempt_id     == attempt_id,
                Question.question_type == QuestionType.mcq,
            )
        )
    )
    mcq_marks = Decimal(str(mcq_r.scalar_one() or 0))

    # Subjective marks
    subj_r = await db.execute(
        select(func.coalesce(
            func.sum(SubjectiveGrade.marks_awarded), 0
        ))
        .join(Answer, SubjectiveGrade.answer_id == Answer.id)
        .where(Answer.attempt_id == attempt_id)
    )
    subj_marks = Decimal(str(subj_r.scalar_one() or 0))

    # Negative marks deducted — stored in existing result row
    # or 0 if not yet computed
    existing_r = await db.execute(
        select(ExamResult).where(
            ExamResult.attempt_id == attempt_id
        )
    )
    existing = existing_r.scalar_one_or_none()
    negative_deducted = (
        existing.negative_marks_deducted
        if existing else Decimal("0.00")
    )

    total = mcq_marks + subj_marks
    # Note: negative marks are already subtracted from mcq_marks
    # at auto-grade time so we don't double-subtract here.
    # negative_marks_deducted is stored for reporting only.

    is_pass = total >= exam.passing_marks

    if existing:
        existing.mcq_marks_awarded        = mcq_marks
        existing.subjective_marks_awarded = subj_marks
        existing.total_marks_awarded      = total
        existing.is_pass                  = is_pass
        existing.computed_at              = ensure_utc(datetime.now(timezone.utc))
        db.add(existing)
    else:
        result_row = ExamResult(
            attempt_id=attempt_id,
            exam_id=exam.id,
            student_id=attempt.student_id,
            mcq_marks_awarded=mcq_marks,
            subjective_marks_awarded=subj_marks,
            negative_marks_deducted=negative_deducted,
            total_marks_awarded=total,
            is_pass=is_pass,
        )
        db.add(result_row)

    await db.flush()

    return {
        "attempt_id":              attempt_id,
        "mcq_marks_awarded":       float(mcq_marks),
        "subjective_marks_awarded": float(subj_marks),
        "negative_marks_deducted": float(negative_deducted),
        "total_marks_awarded":     float(total),
        "is_pass":                 bool(is_pass),
    }


# ── Result publishing ─────────────────────────────────────────────

async def publish_results(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
) -> tuple[bool, str, int]:
    """
    Publishes results for all submitted attempts of an exam.

    Steps:
      1. Verify teacher owns exam.
      2. Compute/update exam_results for every submitted attempt.
      3. Set exam.results_published = True.
      4. Set exam.results_published_at = now(UTC).
      5. Set published_by + published_at on each ExamResult row.

    Returns:
        (True, success_message, published_count)
        (False, error_string, 0)

    Does NOT commit — caller commits.
    """
    from services.exam_service import verify_teacher_owns_exam

    exam = await verify_teacher_owns_exam(
        db, teacher_id, exam_id
    )
    if exam is None:
        return False, "Exam not found or you do not own it.", 0

    if not exam.is_published:
        return False, (
            "Cannot publish results for an unpublished exam."
        ), 0

    if exam.results_published:
        return False, "Results are already published.", 0

    # Fetch all submitted attempts
    attempts_r = await db.execute(
        select(ExamAttempt).where(
            and_(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.status.in_([
                    AttemptStatus.submitted,
                    AttemptStatus.auto_submitted,
                ]),
            )
        )
    )
    attempts = attempts_r.scalars().all()

    now = datetime.now(timezone.utc)
    published_count = 0

    for attempt in attempts:
        # Compute/update result
        await compute_exam_result(db=db, attempt_id=attempt.id)

        # Update published_by + published_at on result row
        await db.execute(
            update(ExamResult)
            .where(ExamResult.attempt_id == attempt.id)
            .values(
                published_by=teacher_id,
                published_at=now,
                is_pass=ExamResult.total_marks_awarded
                        >= exam.passing_marks,
            )
        )
        published_count += 1

    # Mark exam as results published
    exam.results_published    = True
    exam.results_published_at = now
    db.add(exam)

    await db.flush()
    return (
        True,
        f"Results published for {published_count} attempt(s).",
        published_count,
    )


# ── Grade book ────────────────────────────────────────────────────

async def get_grade_book(
    db: AsyncSession,
    exam_id: int,
) -> Optional[dict]:
    """
    Builds the complete grade book for an exam.

    Includes every enrolled student, whether or not they
    attempted the exam.

    Returns a dict matching GradeBookResponse schema,
    or None if exam not found.
    """
    exam_r = await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )
    exam = exam_r.scalar_one_or_none()
    if exam is None:
        return None

    from models import Course
    course_r = await db.execute(
        select(Course).where(Course.id == exam.course_id)
    )
    course = course_r.scalar_one_or_none()
    course_code = course.course_code if course else "—"

    # Get all enrolled students
    enrolled_r = await db.execute(
        select(CourseEnrollment, User)
        .join(User, CourseEnrollment.student_id == User.id)
        .where(CourseEnrollment.course_id == exam.course_id)
        .order_by(User.email.asc())
    )
    enrolled_rows = enrolled_r.all()

    entries   = []
    pass_count = 0
    fail_count = 0
    attempted  = 0
    not_attempted = 0

    for enrollment, user in enrolled_rows:
        # Find attempt
        attempt_r = await db.execute(
            select(ExamAttempt).where(
                and_(
                    ExamAttempt.exam_id    == exam_id,
                    ExamAttempt.student_id == user.id,
                )
            )
        )
        attempt = attempt_r.scalar_one_or_none()

        if attempt is None:
            not_attempted += 1
            entries.append({
                "student_id":               user.id,
                "student_email":            user.email,
                "student_name":             user.full_name,
                "attempt_id":               None,
                "mcq_marks_awarded":        0.0,
                "subjective_marks_awarded": 0.0,
                "negative_marks_deducted":  0.0,
                "total_marks_awarded":      0.0,
                "total_marks_available":    float(exam.total_marks),
                "percentage":               0.0,
                "is_pass":                  False,
                "status":                   "not_attempted",
            })
            continue

        attempted += 1

        # Find result
        result_r = await db.execute(
            select(ExamResult).where(
                ExamResult.attempt_id == attempt.id
            )
        )
        result = result_r.scalar_one_or_none()

        total_marks = float(exam.total_marks)
        if result:
            total_awarded = float(result.total_marks_awarded)
            percentage    = (
                (total_awarded / total_marks * 100)
                if total_marks > 0 else 0.0
            )
            is_pass = bool(result.is_pass) \
                if result.is_pass is not None else None

            if is_pass is True:
                pass_count += 1
            elif is_pass is False:
                fail_count += 1

            entries.append({
                "student_id":               user.id,
                "student_email":            user.email,
                "student_name":             user.full_name,
                "attempt_id":               attempt.id,
                "mcq_marks_awarded":        float(
                    result.mcq_marks_awarded
                ),
                "subjective_marks_awarded": float(
                    result.subjective_marks_awarded
                ),
                "negative_marks_deducted":  float(
                    result.negative_marks_deducted
                ),
                "total_marks_awarded":      total_awarded,
                "total_marks_available":    total_marks,
                "percentage":               round(percentage, 2),
                "is_pass":                  is_pass,
                "status":                   attempt.status.value,
            })
        else:
            # Attempt exists but result not yet computed
            entries.append({
                "student_id":               user.id,
                "student_email":            user.email,
                "student_name":             user.full_name,
                "attempt_id":               attempt.id,
                "mcq_marks_awarded":        0.0,
                "subjective_marks_awarded": 0.0,
                "negative_marks_deducted":  0.0,
                "total_marks_awarded":      0.0,
                "total_marks_available":    total_marks,
                "percentage":               0.0,
                "is_pass":                  None,
                "status":                   attempt.status.value,
            })

    return {
        "exam_id":            exam.id,
        "exam_title":         exam.title,
        "course_code":        course_code,
        "total_marks":        float(exam.total_marks),
        "passing_marks":      float(exam.passing_marks),
        "is_published":       exam.is_published,
        "results_published":  exam.results_published,
        "entries":            entries,
        "attempted_count":    attempted,
        "not_attempted_count": not_attempted,
        "pass_count":         pass_count,
        "fail_count":         fail_count,
    }


# ── Grade book export ─────────────────────────────────────────────

async def export_grade_book_csv(
    db: AsyncSession,
    exam_id: int,
) -> Optional[str]:
    """
    Exports the grade book as a UTF-8 CSV string.

    Columns:
        student_email, student_name, status,
        mcq_marks, subjective_marks, negative_deducted,
        total_marks, available_marks, percentage, pass_fail

    Returns CSV string or None if exam not found.
    """
    grade_book = await get_grade_book(db=db, exam_id=exam_id)
    if grade_book is None:
        return None

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    # Header
    writer.writerow([
        "student_email",
        "student_name",
        "status",
        "mcq_marks_awarded",
        "subjective_marks_awarded",
        "negative_marks_deducted",
        "total_marks_awarded",
        "total_marks_available",
        "percentage",
        "pass_fail",
    ])

    # Data rows
    for entry in grade_book["entries"]:
        writer.writerow([
            entry["student_email"],
            entry["student_name"],
            entry["status"],
            entry["mcq_marks_awarded"],
            entry["subjective_marks_awarded"],
            entry["negative_marks_deducted"],
            entry["total_marks_awarded"],
            entry["total_marks_available"],
            entry["percentage"],
            "PASS" if entry["is_pass"] is True
            else "FAIL" if entry["is_pass"] is False
            else "—",
        ])

    return output.getvalue()


async def export_grade_book_pdf(
    db: AsyncSession,
    exam_id: int,
) -> Optional[bytes]:
    """
    Exports the grade book as a PDF bytes object.
    Uses reportlab (already in requirements.txt).

    Layout:
      - Title: exam title + course code
      - Subtitle: total_marks, passing_marks, results status
      - Summary stats: attempted, not attempted, pass, fail
      - Table: one row per student with all grade columns

    Returns PDF bytes or None if exam not found.
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer,
    )
    from reportlab.lib.styles import getSampleStyleSheet

    grade_book = await get_grade_book(db=db, exam_id=exam_id)
    if grade_book is None:
        return None

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    styles  = getSampleStyleSheet()
    story   = []

    # Title
    story.append(Paragraph(
        f"Grade Book — {grade_book['exam_title']}",
        styles["Title"]
    ))
    story.append(Paragraph(
        f"Course: {grade_book['course_code']} | "
        f"Total Marks: {grade_book['total_marks']} | "
        f"Passing Marks: {grade_book['passing_marks']} | "
        f"Results: {'Published' if grade_book['results_published'] else 'Not Published'}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Attempted: {grade_book['attempted_count']} | "
        f"Not Attempted: {grade_book['not_attempted_count']} | "
        f"Pass: {grade_book['pass_count']} | "
        f"Fail: {grade_book['fail_count']}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.5*cm))

    # Table data
    headers = [
        "Email", "Name", "Status",
        "MCQ", "Subj.", "Neg.",
        "Total", "Avail.", "%", "P/F",
    ]
    rows = [headers]

    for entry in grade_book["entries"]:
        pf = (
            "PASS" if entry["is_pass"] is True
            else "FAIL" if entry["is_pass"] is False
            else "—"
        )
        rows.append([
            entry["student_email"],
            entry["student_name"] or "—",
            entry["status"],
            str(entry["mcq_marks_awarded"]),
            str(entry["subjective_marks_awarded"]),
            str(entry["negative_marks_deducted"]),
            str(entry["total_marks_awarded"]),
            str(entry["total_marks_available"]),
            f"{entry['percentage']}%",
            pf,
        ])

    # Column widths (landscape A4 = ~27.7cm usable)
    col_widths = [
        5.5*cm,  # Email
        3.5*cm,  # Name
        2.5*cm,  # Status
        1.5*cm,  # MCQ
        1.5*cm,  # Subj
        1.5*cm,  # Neg
        1.5*cm,  # Total
        1.5*cm,  # Avail
        1.5*cm,  # %
        1.2*cm,  # P/F
    ]

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        # Data rows
        ("FONTSIZE",    (0, 1), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4ff")]),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",(0, 0), (-1, -1), 4),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0,0), (-1, -1), 3),
        # PASS = green text, FAIL = red text
        *[
            ("TEXTCOLOR", (9, i+1), (9, i+1),
             colors.HexColor("#16a34a")
             if rows[i+1][9] == "PASS"
             else colors.HexColor("#dc2626")
             if rows[i+1][9] == "FAIL"
             else colors.black)
            for i in range(len(grade_book["entries"]))
        ],
    ]))

    story.append(table)
    doc.build(story)

    return buffer.getvalue()
