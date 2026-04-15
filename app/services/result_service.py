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
from core.exceptions import (
    NotFoundException, ForbiddenException, ValidationException, ConflictException
)


# ── Attempt listing for teacher ───────────────────────────────────

async def get_exam_attempts_for_grading(
    db: AsyncSession,
    exam_id: int,
) -> list[dict]:
    """
    Returns a list of all student attempt summaries for an exam.
    Optimized to use bulk queries and aggregations.
    """
    # 1. Get the exam and its course_id
    exam_r = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_r.scalar_one_or_none()
    if not exam:
        return []

    # 2. Get subjective question count for this exam (constant for all students)
    subj_q_count_r = await db.execute(
        select(func.count(Question.id))
        .where(and_(Question.exam_id == exam_id, Question.question_type == QuestionType.subjective))
    )
    subj_q_count = subj_q_count_r.scalar_one()

    # 3. Pre-fetch violation summaries
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
    viol_map = {}
    for aid, vtype, vcount in viols_r.all():
        if aid not in viol_map:
            viol_map[aid] = {}
        viol_map[aid][vtype.value] = vcount

    # 4. Main query: Enrolled students + Attempts + Aggregate marks/grading state
    # We use subqueries for marks to avoid double-counting due to multiple joins
    
    # Subquery for MCQ marks
    mcq_sub = (
        select(Answer.attempt_id, func.sum(Answer.marks_awarded).label("mcq_total"))
        .join(Question, Answer.question_id == Question.id)
        .where(Question.question_type == QuestionType.mcq)
        .group_by(Answer.attempt_id)
        .subquery()
    )

    # Subquery for Subjective marks and graded count
    subj_sub = (
        select(
            Answer.attempt_id, 
            func.sum(SubjectiveGrade.marks_awarded).label("subj_total"),
            func.count(SubjectiveGrade.id).label("graded_count")
        )
        .join(SubjectiveGrade, SubjectiveGrade.answer_id == Answer.id)
        .group_by(Answer.attempt_id)
        .subquery()
    )

    result = await db.execute(
        select(
            User,
            ExamAttempt,
            func.coalesce(mcq_sub.c.mcq_total, 0).label("mcq_marks"),
            func.coalesce(subj_sub.c.subj_total, 0).label("subj_marks"),
            func.coalesce(subj_sub.c.graded_count, 0).label("graded_count")
        )
        .join(CourseEnrollment, CourseEnrollment.student_id == User.id)
        .outerjoin(ExamAttempt, and_(ExamAttempt.student_id == User.id, ExamAttempt.exam_id == exam_id))
        .outerjoin(mcq_sub, mcq_sub.c.attempt_id == ExamAttempt.id)
        .outerjoin(subj_sub, subj_sub.c.attempt_id == ExamAttempt.id)
        .where(CourseEnrollment.course_id == exam.course_id)
        .order_by(User.email.asc())
    )
    rows = result.all()

    summaries = []
    for row in rows:
        user = row.User
        attempt = row.ExamAttempt
        
        if not attempt:
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
            "mcq_marks":           row.mcq_marks,
            "subjective_marks":    row.subj_marks,
            "total_marks_awarded": row.mcq_marks + row.subj_marks,
            "is_fully_graded":     (subj_q_count == 0 or row.graded_count >= subj_q_count),
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
            "marks_available":    question.marks,
            "word_limit":         question.word_limit,
            "selected_option_id": answer.selected_option_id,
            "selected_label":     None,
            "selected_text":      None,
            "correct_label":      None,
            "is_correct":         answer.is_correct,
            "subjective_text":    answer.subjective_text,
            "marks_awarded":      answer.marks_awarded,
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
                entry["marks_awarded"]   = grade.marks_awarded
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
) -> None:
    """
    Submits or updates a teacher's grade for a subjective answer.
    Raises exceptions on failure.
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
        raise NotFoundException(f"Answer {answer_id} not found.")

    answer, question, attempt, exam = row

    if question.question_type != QuestionType.subjective:
        raise ValidationException("Only subjective answers can be manually graded.")

    if Decimal(str(marks_awarded)) > question.marks:
        raise ValidationException(f"marks_awarded ({marks_awarded}) exceeds question's available marks.")

    if not exam.is_published:
        raise ValidationException("Exam is not published.")

    # Only teacher who created exam or admin (implied by router) can grade
    if exam.created_by != teacher_id:
        raise ForbiddenException("You can only grade exams you created.")

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
    return True, f"Grade saved: {marks_awarded} / {question.marks}"


# ── Result computation ────────────────────────────────────────────

async def compute_exam_result(
    db: AsyncSession,
    attempt_id: int,
) -> Optional[dict]:
    """
    Computes and upserts the exam_results row for an attempt.
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

    # MCQ marks
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
        select(func.coalesce(func.sum(SubjectiveGrade.marks_awarded), 0))
        .join(Answer, SubjectiveGrade.answer_id == Answer.id)
        .where(Answer.attempt_id == attempt_id)
    )
    subj_marks = Decimal(str(subj_r.scalar_one() or 0))

    # Negative marks deducted - read from existing result row if it exists
    existing_r = await db.execute(select(ExamResult).where(ExamResult.attempt_id == attempt_id))
    existing = existing_r.scalar_one_or_none()
    negative_deducted = existing.negative_marks_deducted if existing else Decimal("0.00")

    total = mcq_marks + subj_marks
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
        "mcq_marks_awarded":       mcq_marks,
        "subjective_marks_awarded": subj_marks,
        "negative_marks_deducted": negative_deducted,
        "total_marks_awarded":     total,
        "is_pass":                 bool(is_pass),
    }


# ── Result publishing ─────────────────────────────────────────────

async def publish_results(
    db: AsyncSession,
    exam_id: int,
    teacher_id: int,
) -> int:
    """
    Publishes results for all submitted attempts of an exam.
    Returns the count of results published.
    Raises exceptions on failure.
    """
    from services.exam_service import verify_teacher_owns_exam

    exam = await verify_teacher_owns_exam(db, teacher_id, exam_id)
    if exam is None:
        raise ForbiddenException("Exam not found or you do not own it.")

    if not exam.is_published:
        raise ValidationException("Cannot publish results for an unpublished exam.")

    if exam.results_published:
        raise ConflictException("Results are already published.")

    # 1. Get all eligible attempt IDs
    attempts_r = await db.execute(
        select(ExamAttempt.id).where(
            and_(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.status.in_([AttemptStatus.submitted, AttemptStatus.auto_submitted]),
            )
        )
    )
    attempt_ids = [r[0] for r in attempts_r.all()]
    if not attempt_ids:
        # No attempts to publish, but we mark the exam as results_published anyway
        exam.results_published = True
        exam.results_published_at = datetime.now(timezone.utc)
        db.add(exam)
        await db.flush()
        return 0

    # 2. Bulk fetch MCQ totals for all these attempts
    mcq_sums_r = await db.execute(
        select(Answer.attempt_id, func.sum(Answer.marks_awarded).label("mcq_total"))
        .join(Question, Answer.question_id == Question.id)
        .where(and_(Answer.attempt_id.in_(attempt_ids), Question.question_type == QuestionType.mcq))
        .group_by(Answer.attempt_id)
    )
    mcq_map = {r.attempt_id: Decimal(str(r.mcq_total or 0)) for r in mcq_sums_r.all()}

    # 3. Bulk fetch Subjective totals
    subj_sums_r = await db.execute(
        select(Answer.attempt_id, func.sum(SubjectiveGrade.marks_awarded).label("subj_total"))
        .join(SubjectiveGrade, SubjectiveGrade.answer_id == Answer.id)
        .where(Answer.attempt_id.in_(attempt_ids))
        .group_by(Answer.attempt_id)
    )
    subj_map = {r.attempt_id: Decimal(str(r.subj_total or 0)) for r in subj_sums_r.all()}

    # 4. Fetch existing ExamResult rows to update them
    results_r = await db.execute(
        select(ExamResult).where(ExamResult.attempt_id.in_(attempt_ids))
    )
    existing_results = {r.attempt_id: r for r in results_r.scalars().all()}

    now = datetime.now(timezone.utc)
    published_count = 0

    # 5. Update/Create ExamResult rows
    for aid in attempt_ids:
        mcq_val  = mcq_map.get(aid, Decimal("0.00"))
        subj_val = subj_map.get(aid, Decimal("0.00"))
        
        res_row = existing_results.get(aid)
        neg_val = res_row.negative_marks_deducted if res_row else Decimal("0.00")
        
        total   = mcq_val + subj_val
        is_pass = total >= exam.passing_marks

        if res_row:
            res_row.mcq_marks_awarded        = mcq_val
            res_row.subjective_marks_awarded = subj_val
            res_row.total_marks_awarded      = total
            res_row.is_pass                  = is_pass
            res_row.published_by             = teacher_id
            res_row.published_at             = now
            res_row.computed_at              = now
            db.add(res_row)
        else:
            # This shouldn't normally happen if student_service.py was called correctly,
            # but we handle it for robustness.
            new_res = ExamResult(
                attempt_id=aid,
                exam_id=exam_id,
                student_id=None, # We'd need to fetch this if we really wanted to be robust
                mcq_marks_awarded=mcq_val,
                subjective_marks_awarded=subj_val,
                negative_marks_deducted=Decimal("0.00"),
                total_marks_awarded=total,
                is_pass=is_pass,
                published_by=teacher_id,
                published_at=now,
            )
            db.add(new_res)
        
        published_count += 1

    # 6. Mark exam as results published
    exam.results_published    = True
    exam.results_published_at = now
    db.add(exam)

    await db.flush()
    return True, f"Results published for {published_count} attempt(s).", published_count



# ── Grade book ────────────────────────────────────────────────────

async def get_grade_book(
    db: AsyncSession,
    exam_id: int,
) -> Optional[dict]:
    """
    Builds the complete grade book for an exam.
    Includes every enrolled student, whether or not they attempted the exam.
    Optimized to use a single bulk query.
    """
    exam_r = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_r.scalar_one_or_none()
    if not exam:
        return None

    from models import Course
    course_r = await db.execute(select(Course).where(Course.id == exam.course_id))
    course = course_r.scalar_one_or_none()
    course_code = course.course_code if course else "—"

    # Single bulk query for all enrolled students, their attempts, and results
    result = await db.execute(
        select(User, ExamAttempt, ExamResult)
        .join(CourseEnrollment, CourseEnrollment.student_id == User.id)
        .outerjoin(ExamAttempt, and_(ExamAttempt.student_id == User.id, ExamAttempt.exam_id == exam_id))
        .outerjoin(ExamResult, ExamResult.attempt_id == ExamAttempt.id)
        .where(CourseEnrollment.course_id == exam.course_id)
        .order_by(User.email.asc())
    )
    rows = result.all()

    entries = []
    pass_count = 0
    fail_count = 0
    attempted_count = 0
    not_attempted_count = 0
    total_marks_available = exam.total_marks

    for row in rows:
        user = row.User
        attempt = row.ExamAttempt
        res_row = row.ExamResult

        if not attempt:
            not_attempted_count += 1
            entries.append({
                "student_id":               user.id,
                "student_email":            user.email,
                "student_name":             user.full_name,
                "attempt_id":               None,
                "mcq_marks_awarded":        0.0,
                "subjective_marks_awarded": 0.0,
                "negative_marks_deducted":  0.0,
                "total_marks_awarded":      0.0,
                "total_marks_available":    total_marks_available,
                "percentage":               0.0,
                "is_pass":                  None,
                "status":                   "not_attempted",
            })
            continue

        attempted_count += 1
        
        if res_row:
            total_awarded = res_row.total_marks_awarded
            percentage = (total_awarded / total_marks_available * 100) if total_marks_available > 0 else Decimal("0.0")
            is_pass = bool(res_row.is_pass)

            if is_pass:
                pass_count += 1
            else:
                fail_count += 1

            entries.append({
                "student_id":               user.id,
                "student_email":            user.email,
                "student_name":             user.full_name,
                "attempt_id":               attempt.id,
                "mcq_marks_awarded":        res_row.mcq_marks_awarded,
                "subjective_marks_awarded": res_row.subjective_marks_awarded,
                "negative_marks_deducted":  res_row.negative_marks_deducted,
                "total_marks_awarded":      total_awarded,
                "total_marks_available":    total_marks_available,
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
                "total_marks_available":    total_marks_available,
                "percentage":               0.0,
                "is_pass":                  None,
                "status":                   attempt.status.value,
            })

    return {
        "exam_id":             exam.id,
        "exam_title":          exam.title,
        "course_code":         course_code,
        "total_marks":         total_marks_available,
        "passing_marks":       exam.passing_marks,
        "is_published":        exam.is_published,
        "results_published":   exam.results_published,
        "total_enrolled":      len(rows),
        "attempted_count":     attempted_count,
        "not_attempted_count": not_attempted_count,
        "pass_count":          pass_count,
        "fail_count":          fail_count,
        "entries":             entries,
    }


# ── Grade book export ─────────────────────────────────────────────

async def export_grade_book_csv(
    db: AsyncSession,
    exam_id: int,
) -> Optional[str]:
    """
    Exports the grade book as a UTF-8 CSV string.
    """
    grade_book = await get_grade_book(db=db, exam_id=exam_id)
    if grade_book is None:
        return None

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    writer.writerow([
        "student_email", "student_name", "status",
        "mcq_marks_awarded", "subjective_marks_awarded", "negative_marks_deducted",
        "total_marks_awarded", "total_marks_available", "percentage", "pass_fail",
    ])

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
            "PASS" if entry["is_pass"] is True else "FAIL" if entry["is_pass"] is False else "—",
        ])

    return output.getvalue()


async def export_grade_book_pdf(
    db: AsyncSession,
    exam_id: int,
) -> Optional[bytes]:
    """
    Exports the grade book as a PDF bytes object.
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    grade_book = await get_grade_book(db=db, exam_id=exam_id)
    if grade_book is None:
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Grade Book — {grade_book['exam_title']}", styles["Title"]))
    story.append(Paragraph(
        f"Course: {grade_book['course_code']} | Total Marks: {grade_book['total_marks']} | "
        f"Passing Marks: {grade_book['passing_marks']} | "
        f"Results: {'Published' if grade_book['results_published'] else 'Not Published'}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Attempted: {grade_book['attempted_count']} | Not Attempted: {grade_book['not_attempted_count']} | "
        f"Pass: {grade_book['pass_count']} | Fail: {grade_book['fail_count']}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.5*cm))

    headers = ["Email", "Name", "Status", "MCQ", "Subj.", "Neg.", "Total", "Avail.", "%", "P/F"]
    table_data = [headers]

    for entry in grade_book["entries"]:
        pf = "PASS" if entry["is_pass"] is True else "FAIL" if entry["is_pass"] is False else "—"
        table_data.append([
            entry["student_email"], entry["student_name"], entry["status"],
            entry["mcq_marks_awarded"], entry["subjective_marks_awarded"], entry["negative_marks_deducted"],
            entry["total_marks_awarded"], entry["total_marks_available"], entry["percentage"], pf
        ])

    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)

    doc.build(story)
    return buffer.getvalue()
