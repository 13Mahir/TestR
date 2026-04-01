"""
routers/teacher.py
Teacher panel API endpoints.
All routes prefixed with /api/teacher in main.py.

This prompt implements:
  - GET  /api/teacher/courses            (assigned courses)
  - POST /api/teacher/exams              (create exam)
  - GET  /api/teacher/exams              (list own exams)
  - GET  /api/teacher/exams/{id}         (get single exam)
  - PATCH /api/teacher/exams/{id}        (update exam)
  - DELETE /api/teacher/exams/{id}       (delete exam)
  - POST /api/teacher/exams/{id}/publish (publish exam)
  - GET  /api/teacher/exams/{id}/questions (list questions)
  - POST /api/teacher/exams/{id}/questions/mcq
  - POST /api/teacher/exams/{id}/questions/subjective
  - DELETE /api/teacher/questions/{question_id}

Grading + result publishing added in Prompt 16.
"""

from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException,
    Request, Query, status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_active_teacher
from models import User, SystemLogEventType
from schemas.teacher import (
    AssignedCourseOut,
    ExamCreateRequest,
    ExamUpdateRequest,
    ExamOut,
    ExamListResponse,
    MCQQuestionCreateRequest,
    SubjectiveQuestionCreateRequest,
    QuestionOut,
    MCQOptionOut,
)
from services.exam_service import (
    get_assigned_courses,
    create_exam,
    get_exam_by_id,
    list_exams_for_teacher,
    update_exam,
    delete_exam,
    publish_exam,
    add_mcq_question,
    add_subjective_question,
    get_exam_questions,
    delete_question,
)
from services.log_service import write_system_log
from services import proctor_service

from fastapi.responses import StreamingResponse
import io
from services.result_service import (
    get_exam_attempts_for_grading,
    get_student_answers_for_grading,
    grade_subjective_answer,
    publish_results,
    get_grade_book,
    export_grade_book_csv,
    export_grade_book_pdf,
)
from schemas.teacher import (
    StudentAnswerOut,
    StudentAttemptSummary,
    SubjectiveGradeRequest,
    GradeBookEntryOut,
    GradeBookResponse,
)

router = APIRouter(tags=["teacher"])


def _get_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── GET /api/teacher/courses ──────────────────────────────────────

@router.get(
    "/courses",
    summary="List all courses assigned to the teacher.",
)
async def list_assigned_courses(
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> dict:
    """
    Returns all courses the teacher is assigned to,
    with enrollment counts and assignment date.
    Not paginated — a teacher rarely has more than 10 courses.
    """
    courses = await get_assigned_courses(
        db=db, teacher_id=teacher.id
    )
    return {"items": courses, "total": len(courses)}


# ── POST /api/teacher/exams ───────────────────────────────────────

@router.post(
    "/exams",
    response_model=ExamOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new exam for an assigned course.",
)
async def create_exam_endpoint(
    body:    ExamCreateRequest,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> ExamOut:
    """
    Creates a new exam. Teacher must be assigned to the course.

    Validates:
      - Teacher is assigned to course_id.
      - Course is active.
      - No overlapping exam exists for this course + time window.
      - end_time > start_time.
      - duration_minutes fits within the time window.

    Writes system_log: event_type='exam_created'.
    """
    exam, error = await create_exam(
        db=db,
        course_id=body.course_id,
        teacher_id=teacher.id,
        title=body.title,
        description=body.description,
        duration_minutes=body.duration_minutes,
        negative_marking_factor=body.negative_marking_factor,
        passing_marks=body.passing_marks,
        start_time=body.start_time,
        end_time=body.end_time,
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    await write_system_log(
        db=db,
        event_type=SystemLogEventType.exam_created,
        actor_id=teacher.id,
        description=(
            f"Exam created: '{exam.title}' for course "
            f"{body.course_id}"
        ),
        metadata={
            "exam_id":   exam.id,
            "course_id": body.course_id,
            "title":     exam.title,
        },
    )

    exam_dict = await get_exam_by_id(db=db, exam_id=exam.id)
    return ExamOut(**exam_dict)


# ── GET /api/teacher/exams ────────────────────────────────────────

@router.get(
    "/exams",
    response_model=ExamListResponse,
    summary="List exams created by the teacher.",
)
async def list_exams(
    course_id:    Optional[int]  = Query(None),
    is_published: Optional[bool] = Query(None),
    page:         int = Query(default=1, ge=1),
    page_size:    int = Query(default=20, ge=1, le=100),
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> ExamListResponse:
    """
    Returns paginated exams created by this teacher.
    Optionally filtered by course_id and published state.
    """
    exams, total = await list_exams_for_teacher(
        db=db,
        teacher_id=teacher.id,
        course_id=course_id,
        is_published=is_published,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    total_pages = max(1, -(-total // page_size))

    return ExamListResponse(
        items=[ExamOut(**e) for e in exams],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


# ── GET /api/teacher/exams/{exam_id} ─────────────────────────────

@router.get(
    "/exams/{exam_id}",
    response_model=ExamOut,
    summary="Get a single exam by ID.",
)
async def get_exam(
    exam_id: int,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> ExamOut:
    """
    Returns a single exam. Teacher must own the exam.
    """
    exam_dict = await get_exam_by_id(db=db, exam_id=exam_id)
    if exam_dict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam {exam_id} not found.",
        )
    if exam_dict["course_id"] not in [
        c["id"] for c in
        await get_assigned_courses(db, teacher.id)
    ]:
        # Additional check: exam must belong to a course
        # this teacher is assigned to
        from services.exam_service import verify_teacher_owns_exam
        exam_obj = await verify_teacher_owns_exam(
            db, teacher.id, exam_id
        )
        if exam_obj is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this exam.",
            )
    return ExamOut(**exam_dict)


# ── PATCH /api/teacher/exams/{exam_id} ───────────────────────────

@router.patch(
    "/exams/{exam_id}",
    response_model=ExamOut,
    summary="Update an unpublished exam.",
)
async def update_exam_endpoint(
    exam_id: int,
    body:    ExamUpdateRequest,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> ExamOut:
    """
    Updates mutable fields of an exam.
    Cannot update a published exam.
    Only provided (non-None) fields are updated.
    """
    ok, msg = await update_exam(
        db=db,
        exam_id=exam_id,
        teacher_id=teacher.id,
        **body.model_dump(exclude_none=True),
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    await db.commit()
    exam_dict = await get_exam_by_id(db=db, exam_id=exam_id)
    return ExamOut(**exam_dict)


# ── DELETE /api/teacher/exams/{exam_id} ──────────────────────────

@router.delete(
    "/exams/{exam_id}",
    summary="Delete an unpublished exam with no attempts.",
)
async def delete_exam_endpoint(
    exam_id: int,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> dict:
    """
    Deletes an exam. Only allowed if unpublished and
    no student attempts exist.
    """
    ok, msg = await delete_exam(
        db=db,
        exam_id=exam_id,
        teacher_id=teacher.id,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    await db.commit()
    return {"message": msg}


# ── POST /api/teacher/exams/{exam_id}/publish ─────────────────────

@router.post(
    "/exams/{exam_id}/publish",
    summary="Publish an exam to make it visible to students.",
)
async def publish_exam_endpoint(
    exam_id: int,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> dict:
    """
    Publishes an exam.

    Pre-publish checks:
      - At least 1 question exists.
      - start_time is in the future.
      - passing_marks <= total_marks.

    After publishing the exam is visible in the student
    exam lobby within the 5-minute window around start_time.

    Writes system_log: event_type='exam_published'.
    Sends in-app notification to all enrolled students.
    """
    ok, msg = await publish_exam(
        db=db,
        exam_id=exam_id,
        teacher_id=teacher.id,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # Load exam for logging + notifications
    exam_dict = await get_exam_by_id(db=db, exam_id=exam_id)

    await write_system_log(
        db=db,
        event_type=SystemLogEventType.exam_published,
        actor_id=teacher.id,
        description=(
            f"Exam published: '{exam_dict['title']}' "
            f"(course {exam_dict['course_id']})"
        ),
        metadata={
            "exam_id":   exam_id,
            "course_id": exam_dict["course_id"],
            "title":     exam_dict["title"],
        },
    )

    # Notify enrolled students
    from models import CourseEnrollment
    from services.notification_service import (
        create_notifications_bulk
    )
    from sqlalchemy import select as sa_select

    enrolled_r = await db.execute(
        sa_select(CourseEnrollment.student_id)
        .where(
            CourseEnrollment.course_id == exam_dict["course_id"]
        )
    )
    student_ids = [row[0] for row in enrolled_r.all()]

    if student_ids:
        await create_notifications_bulk(
            db=db,
            user_ids=student_ids,
            type="EXAM_PUBLISHED",
            title=f"New Exam: {exam_dict['title']}",
            body=(
                f"Exam '{exam_dict['title']}' for course {exam_dict['course_code']} "
                f"is now available. Starts: {exam_dict['start_time']}."
            ),
            link="/student/exams"
        )

    return {
        "message": msg,
        "exam_id": exam_id,
        "notified_students": len(student_ids),
    }


# ── GET /api/teacher/exams/{exam_id}/questions ───────────────────

@router.get(
    "/exams/{exam_id}/questions",
    summary="List all questions for an exam.",
)
async def list_questions(
    exam_id: int,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> dict:
    """
    Returns all questions for an exam, ordered by order_index.
    Includes MCQ options with is_correct flag (teacher view).
    Teacher must own the exam.
    """
    from services.exam_service import verify_teacher_owns_exam
    exam = await verify_teacher_owns_exam(
        db, teacher.id, exam_id
    )
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam not found or you do not own it.",
        )

    questions = await get_exam_questions(
        db=db, exam_id=exam_id
    )
    return {
        "exam_id": exam_id,
        "items":   questions,
        "total":   len(questions),
    }


# ── POST /api/teacher/exams/{exam_id}/questions/mcq ──────────────

@router.post(
    "/exams/{exam_id}/questions/mcq",
    status_code=status.HTTP_201_CREATED,
    summary="Add an MCQ question to an exam.",
)
async def add_mcq(
    exam_id: int,
    body:    MCQQuestionCreateRequest,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> dict:
    """
    Adds an MCQ question with 2-4 options.
    Exactly one option must be marked is_correct=True.
    Recomputes exam.total_marks automatically.
    """
    question, error = await add_mcq_question(
        db=db,
        exam_id=exam_id,
        teacher_id=teacher.id,
        question_text=body.question_text,
        marks=body.marks,
        order_index=body.order_index,
        options=[o.model_dump() for o in body.options],
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    # Return the created question with options
    questions = await get_exam_questions(
        db=db, exam_id=exam_id
    )
    created = next(
        (q for q in questions if q["id"] == question.id), None
    )

    # Also return updated total_marks
    exam_dict = await get_exam_by_id(db=db, exam_id=exam_id)

    return {
        "question":    created,
        "total_marks": exam_dict["total_marks"],
        "message":     "MCQ question added successfully.",
    }


# ── POST /api/teacher/exams/{exam_id}/questions/subjective ───────

@router.post(
    "/exams/{exam_id}/questions/subjective",
    status_code=status.HTTP_201_CREATED,
    summary="Add a subjective question to an exam.",
)
async def add_subjective(
    exam_id: int,
    body:    SubjectiveQuestionCreateRequest,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> dict:
    """
    Adds a subjective (descriptive) question.
    Optional word_limit constrains the student's answer.
    Recomputes exam.total_marks automatically.
    """
    question, error = await add_subjective_question(
        db=db,
        exam_id=exam_id,
        teacher_id=teacher.id,
        question_text=body.question_text,
        marks=body.marks,
        order_index=body.order_index,
        word_limit=body.word_limit,
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    exam_dict = await get_exam_by_id(db=db, exam_id=exam_id)

    return {
        "question": {
            "id":            question.id,
            "exam_id":       question.exam_id,
            "question_text": question.question_text,
            "question_type": question.question_type.value,
            "marks":         float(question.marks),
            "order_index":   question.order_index,
            "word_limit":    question.word_limit,
            "options":       [],
        },
        "total_marks": exam_dict["total_marks"],
        "message":     "Subjective question added successfully.",
    }


# ── DELETE /api/teacher/questions/{question_id} ──────────────────

@router.delete(
    "/questions/{question_id}",
    summary="Delete a question from an unpublished exam.",
)
async def delete_question_endpoint(
    question_id: int,
    db:          AsyncSession = Depends(get_db),
    teacher:     User         = Depends(get_active_teacher),
) -> dict:
    """
    Deletes a question. Only allowed on unpublished exams.
    Recomputes total_marks after deletion.
    """
    ok, msg = await delete_question(
        db=db,
        question_id=question_id,
        teacher_id=teacher.id,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    return {"message": msg}


# ── GET /api/teacher/exams/{exam_id}/attempts ─────────────────────

@router.get(
    "/exams/{exam_id}/attempts",
    summary="List all student attempts for an exam (grading view).",
)
async def list_attempts_for_grading(
    exam_id: int,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> dict:
    """
    Returns all enrolled students and their attempt status
    for an exam. Used by the teacher grading list page.

    Students who have not attempted are included with
    status='not_attempted'.

    Teacher must own the exam.
    """
    from services.exam_service import verify_teacher_owns_exam
    exam = await verify_teacher_owns_exam(
        db, teacher.id, exam_id
    )
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam not found or you do not own it.",
        )

    summaries = await get_exam_attempts_for_grading(
        db=db, exam_id=exam_id
    )
    return {
        "exam_id": exam_id,
        "items":   summaries,
        "total":   len(summaries),
    }


# ── GET /api/teacher/exams/{exam_id}/attempts/{attempt_id} ───────

@router.get(
    "/exams/{exam_id}/attempts/{attempt_id}",
    summary="Get all answers for a student's attempt (grading detail).",
)
async def get_attempt_answers(
    exam_id:    int,
    attempt_id: int,
    db:         AsyncSession = Depends(get_db),
    teacher:    User         = Depends(get_active_teacher),
) -> dict:
    """
    Returns all questions and the student's answers for
    a single attempt. Includes:
      - MCQ: selected option, correct option, auto-grade result
      - Subjective: student's text, existing grade if any

    Teacher must own the exam.
    """
    from services.exam_service import verify_teacher_owns_exam
    exam = await verify_teacher_owns_exam(
        db, teacher.id, exam_id
    )
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam not found or you do not own it.",
        )

    # Verify attempt belongs to this exam
    from sqlalchemy import select as sa_select
    from models import ExamAttempt as EA
    from sqlalchemy import and_
    attempt_r = await db.execute(
        sa_select(EA).where(
            and_(EA.id == attempt_id, EA.exam_id == exam_id)
        )
    )
    attempt = attempt_r.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found for this exam.",
        )

    answers = await get_student_answers_for_grading(
        db=db, attempt_id=attempt_id
    )
    return {
        "exam_id":    exam_id,
        "attempt_id": attempt_id,
        "items":      answers,
        "total":      len(answers),
    }


# ── POST /api/teacher/exams/{id}/grade/{attempt_id}/{answer_id} ──

@router.post(
    "/exams/{exam_id}/grade/{attempt_id}/{answer_id}",
    summary="Submit or update a subjective grade.",
)
async def submit_grade(
    exam_id:    int,
    attempt_id: int,
    answer_id:  int,
    body:       SubjectiveGradeRequest,
    db:         AsyncSession = Depends(get_db),
    teacher:    User         = Depends(get_active_teacher),
) -> dict:
    """
    Saves a teacher's grade for a subjective answer.

    Can be called multiple times — subsequent calls update
    the existing grade (not create duplicates).

    marks_awarded must be >= 0 and <= question's available marks.
    """
    from services.exam_service import verify_teacher_owns_exam
    exam = await verify_teacher_owns_exam(
        db, teacher.id, exam_id
    )
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam not found or you do not own it.",
        )

    ok, msg = await grade_subjective_answer(
        db=db,
        answer_id=answer_id,
        teacher_id=teacher.id,
        marks_awarded=body.marks_awarded,
        feedback=body.feedback,
    )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    return {"message": msg}


# ── POST /api/teacher/exams/{exam_id}/publish-results ────────────

@router.post(
    "/exams/{exam_id}/publish-results",
    summary="Publish exam results — students can now see scores.",
)
async def publish_results_endpoint(
    exam_id: int,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> dict:
    """
    Computes and publishes results for all submitted attempts.

    After this call:
      - exam.results_published = True
      - Students can see their scores on their dashboard
      - In-app notifications sent to all students who attempted

    Writes system_log: event_type='results_published'.
    """
    ok, msg, count = await publish_results(
        db=db,
        exam_id=exam_id,
        teacher_id=teacher.id,
    )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # System log
    from sqlalchemy import select
    from models import Exam as ExamModel
    exam_r = await db.execute(
        select(ExamModel).where(ExamModel.id == exam_id)
    )
    exam_obj = exam_r.scalar_one_or_none()

    await write_system_log(
        db=db,
        event_type=SystemLogEventType.results_published,
        actor_id=teacher.id,
        description=(
            f"Results published for exam '{exam_obj.title}' "
            f"— {count} result(s) finalised."
        ),
        metadata={
            "exam_id":         exam_id,
            "published_count": count,
        },
    )

    # Notify students who have attempts
    from models import ExamAttempt as EA, AttemptStatus as AS
    from sqlalchemy import and_
    from services.notification_service import (
        create_notifications_bulk
    )

    attempts_r = await db.execute(
        select(EA.student_id).where(
            and_(
                EA.exam_id == exam_id,
                EA.status.in_([
                    AS.submitted,
                    AS.auto_submitted,
                ]),
            )
        )
    )
    student_ids = [row[0] for row in attempts_r.all()]

    if student_ids:
        await create_notifications_bulk(
            db=db,
            user_ids=student_ids,
            type="RESULTS_PUBLISHED",
            title=f"Results Published: {exam_obj.title}",
            body=(
                f"Scores for your attempt at '{exam_obj.title}' "
                f"are now available on your dashboard."
            ),
            link="/student/transcript"
        )

    return {"message": msg, "finalised_count": count}


# ── GET /api/teacher/attempts/{attempt_id}/violations ───────────

@router.get(
    "/attempts/{attempt_id}/violations",
    summary="List all proctor violations for a student's attempt.",
)
async def get_attempt_violations(
    attempt_id: int,
    db:         AsyncSession = Depends(get_db),
    teacher:    User         = Depends(get_active_teacher),
) -> dict:
    """
    Returns a chronological list of proctor violations (tab switch, etc).
    Teacher must own the exam associated with the attempt.
    """
    from services.exam_service import verify_teacher_owns_exam
    from models import ExamAttempt
    
    # 1. Fetch attempt to get exam_id
    attempt_r = await db.execute(
        select(ExamAttempt).where(ExamAttempt.id == attempt_id)
    )
    attempt = attempt_r.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    # 2. Verify ownership
    exam = await verify_teacher_owns_exam(db, teacher.id, attempt.exam_id)
    if not exam:
        raise HTTPException(status_code=403, detail="Access denied")
        
    violations = await proctor_service.get_violations_for_attempt(db, attempt_id)
    return {"attempt_id": attempt_id, "items": violations}


# ── GET /api/teacher/attempts/{attempt_id}/snapshots ────────────

@router.get(
    "/attempts/{attempt_id}/snapshots",
    summary="List all proctor camera snapshots for a student's attempt.",
)
async def get_attempt_snapshots(
    attempt_id: int,
    db:         AsyncSession = Depends(get_db),
    teacher:    User         = Depends(get_active_teacher),
) -> dict:
    """
    Returns all snapshots with signed GCS URLs.
    Teacher must own the exam associated with the attempt.
    """
    from services.exam_service import verify_teacher_owns_exam
    from models import ExamAttempt
    
    # 1. Fetch attempt to get exam_id
    attempt_r = await db.execute(
        select(ExamAttempt).where(ExamAttempt.id == attempt_id)
    )
    attempt = attempt_r.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    # 2. Verify ownership
    exam = await verify_teacher_owns_exam(db, teacher.id, attempt.exam_id)
    if not exam:
        raise HTTPException(status_code=403, detail="Access denied")
        
    snapshots = await proctor_service.get_snapshots_for_attempt(db, attempt_id)
    return {"attempt_id": attempt_id, "items": snapshots}


# ── GET /api/teacher/exams/{exam_id}/gradebook ───────────────────

@router.get(
    "/exams/{exam_id}/gradebook",
    response_model=GradeBookResponse,
    summary="Get the complete grade book for an exam.",
)
async def get_gradebook(
    exam_id: int,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> GradeBookResponse:
    """
    Returns the complete grade book for an exam including
    all enrolled students (attempted and not attempted).

    Teacher must own the exam.
    """
    from services.exam_service import verify_teacher_owns_exam
    exam = await verify_teacher_owns_exam(
        db, teacher.id, exam_id
    )
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam not found or you do not own it.",
        )

    grade_book = await get_grade_book(db=db, exam_id=exam_id)
    if grade_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam {exam_id} not found.",
        )

    return GradeBookResponse(**grade_book)


# ── GET /api/teacher/exams/{exam_id}/gradebook/export/csv ────────

@router.get(
    "/exams/{exam_id}/gradebook/export/csv",
    summary="Export grade book as CSV download.",
)
async def export_gradebook_csv(
    exam_id: int,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> StreamingResponse:
    """
    Downloads the grade book as a CSV file.
    Filename: gradebook_{course_code}_{exam_id}.csv
    """
    from services.exam_service import verify_teacher_owns_exam
    exam = await verify_teacher_owns_exam(
        db, teacher.id, exam_id
    )
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam not found or you do not own it.",
        )

    csv_str = await export_grade_book_csv(
        db=db, exam_id=exam_id
    )
    if csv_str is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    filename = f"gradebook_{exam_id}.csv"

    return StreamingResponse(
        content=io.StringIO(csv_str),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f"attachment; filename={filename}",
        },
    )


# ── GET /api/teacher/exams/{exam_id}/gradebook/export/pdf ────────

@router.get(
    "/exams/{exam_id}/gradebook/export/pdf",
    summary="Export grade book as PDF download.",
)
async def export_gradebook_pdf(
    exam_id: int,
    db:      AsyncSession = Depends(get_db),
    teacher: User         = Depends(get_active_teacher),
) -> StreamingResponse:
    """
    Downloads the grade book as a formatted PDF file.
    Uses reportlab. Landscape A4 with alternating row colours.
    Filename: gradebook_{exam_id}.pdf
    """
    from services.exam_service import verify_teacher_owns_exam
    exam = await verify_teacher_owns_exam(
        db, teacher.id, exam_id
    )
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam not found or you do not own it.",
        )

    pdf_bytes = await export_grade_book_pdf(
        db=db, exam_id=exam_id
    )
    if pdf_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    filename = f"gradebook_{exam_id}.pdf"

    return StreamingResponse(
        content=io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f"attachment; filename={filename}",
        },
    )
