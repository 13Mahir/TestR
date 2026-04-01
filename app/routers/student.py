"""
routers/student.py
Student panel API endpoints.
All routes prefixed with /api/student in main.py.

This prompt implements:
  GET /api/student/courses
  GET /api/student/dashboard
  GET /api/student/transcript
  GET /api/student/exams/{exam_id}/lobby
  GET /api/student/exams (upcoming exams list)

Exam attempt endpoints added in Prompt 20.
"""

from typing import Optional
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, HTTPException,
    Query, status, Request,
)
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_active_student
from core.utils import ensure_utc
from models import User, ExamAttempt, Answer, AttemptStatus
from schemas.student import (
    EnrolledCourseOut,
    UpcomingExamOut,
    RecentResultOut,
    SubjectPerformanceOut,
    TranscriptEntryOut,
    ExamLobbyOut,
)
from services.student_service import (
    get_enrolled_courses,
    get_recent_results,
    get_subject_performance,
    get_upcoming_exams,
    get_transcript,
    check_exam_eligibility,
    start_exam_attempt,
    get_exam_questions_for_student,
    save_answer,
    submit_attempt,
    get_attempt_status,
    log_proctor_violation,
)
from services.user_service import log_ip_event

router = APIRouter(tags=["student"])


# ── GET /api/student/courses ──────────────────────────────────────

@router.get(
    "/courses",
    summary="List all courses the student is enrolled in.",
)
async def list_enrolled_courses(
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> dict:
    """
    Returns all enrolled courses with upcoming + completed
    exam counts.
    """
    courses = await get_enrolled_courses(
        db=db, student_id=student.id
    )
    return {"items": courses, "total": len(courses)}


# ── GET /api/student/dashboard ────────────────────────────────────

@router.get(
    "/dashboard",
    summary="Student dashboard: recent results + upcoming exams + performance.",
)
async def get_dashboard(
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> dict:
    """
    Returns all data needed for the student dashboard in one call:
      - recent_results: last 5 published results
      - upcoming_exams: next 5 published exams not yet attempted
      - subject_performance: per-course average scores
      - summary: total attempted, pass rate, overall average
    """
    recent      = await get_recent_results(
        db=db, student_id=student.id, limit=5
    )
    upcoming    = await get_upcoming_exams(
        db=db, student_id=student.id, limit=5
    )
    performance = await get_subject_performance(
        db=db, student_id=student.id
    )

    # Summary stats
    total_attempted = sum(
        p["exams_attempted"] for p in performance
    )
    total_pass      = sum(p["pass_count"] for p in performance)
    pass_rate       = (
        round(total_pass / total_attempted * 100, 1)
        if total_attempted > 0 else 0
    )
    avg_pct         = (
        round(
            sum(p["average_pct"] for p in performance)
            / len(performance),
            1,
        )
        if performance else 0
    )

    return {
        "recent_results":     recent,
        "upcoming_exams":     upcoming,
        "subject_performance": performance,
        "summary": {
            "total_attempted": total_attempted,
            "total_pass":      total_pass,
            "pass_rate":       pass_rate,
            "average_pct":     avg_pct,
        },
    }


# ── GET /api/student/exams ────────────────────────────────────────

@router.get(
    "/exams",
    summary="List upcoming published exams for enrolled courses.",
)
async def list_upcoming_exams(
    limit:   int = Query(default=20, ge=1, le=100),
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> dict:
    """
    Returns upcoming published exams across all enrolled courses.
    Includes has_attempted flag for each exam.
    """
    exams = await get_upcoming_exams(
        db=db, student_id=student.id, limit=limit
    )
    return {"items": exams, "total": len(exams)}


# ── GET /api/student/transcript ───────────────────────────────────

@router.get(
    "/transcript",
    summary="Full academic transcript — all published results.",
)
async def get_student_transcript(
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> dict:
    """
    Returns all published exam results across all courses.
    Includes percentage and pass/fail status.
    Used for the student transcript page.
    """
    entries = await get_transcript(
        db=db, student_id=student.id
    )

    # Compute overall GPA-style summary
    total_pct   = sum(e["percentage"] for e in entries)
    overall_avg = (
        round(total_pct / len(entries), 2)
        if entries else 0.0
    )
    pass_count  = sum(
        1 for e in entries if e["is_pass"] is True
    )

    return {
        "entries":       entries,
        "total":         len(entries),
        "overall_avg":   overall_avg,
        "pass_count":    pass_count,
        "fail_count":    sum(
            1 for e in entries if e["is_pass"] is False
        ),
    }


# ── GET /api/student/exams/{exam_id}/lobby ────────────────────────

@router.get(
    "/exams/{exam_id}/lobby",
    response_model=ExamLobbyOut,
    summary="Check exam eligibility and get lobby info.",
)
async def exam_lobby(
    exam_id: int,
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> ExamLobbyOut:
    """
    Returns exam details and eligibility status.
    Clients poll this endpoint to detect when the exam starts.

    can_attempt=True  → student may call POST /api/student/attempts
                        to start the exam.
    can_attempt=False → reason field explains why.

    5-minute pre-start window:
      - Student can view the lobby page when minutes_until_start <= 5
      - But can only start (POST /attempts) when start_time has passed
        (enforced in Prompt 20 attempt endpoint)
    """
    result = await check_exam_eligibility(
        db=db,
        student_id=student.id,
        exam_id=exam_id,
    )

    # If exam_id not found, return 404
    if "title" not in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("reason", "Exam not found."),
        )

    return ExamLobbyOut(**result)


# ── POST /api/student/attempts ────────────────────────────────────

@router.post(
    "/attempts",
    status_code=status.HTTP_201_CREATED,
    summary="Start a new exam attempt.",
)
async def start_attempt(
    exam_id: int = Query(..., description="Exam ID to attempt"),
    request: Request = None,
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> dict:
    """
    Creates a new ExamAttempt. Must be called within the
    exam's start_time to end_time window.

    After this call the client should:
      1. GET /api/student/attempts/{attempt_id}/questions
         to fetch questions.
      2. POST /api/student/attempts/{attempt_id}/answers
         to save each answer.
      3. POST /api/student/attempts/{attempt_id}/submit
         to submit when done or when timer expires.

    Logs ip_address to ip_logs with action='exam_attempt_start'.
    """
    ip = _get_ip(request)

    attempt, error = await start_exam_attempt(
        db=db,
        student_id=student.id,
        exam_id=exam_id,
        ip_address=ip,
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    # Log the attempt start
    await log_ip_event(
        db=db,
        action="exam_attempt_start",
        ip_address=ip,
        email_attempted=student.email,
        user_id=student.id,
    )

    return {
        "attempt_id": attempt.id,
        "exam_id":    attempt.exam_id,
        "started_at": ensure_utc(attempt.started_at),
        "status":     attempt.status.value,
        "message":    "Attempt started. Good luck!",
    }


# ── GET /api/student/attempts/{attempt_id}/questions ─────────────

@router.get(
    "/attempts/{attempt_id}/questions",
    summary="Fetch questions for an in-progress attempt.",
)
async def get_attempt_questions(
    attempt_id: int,
    db:         AsyncSession = Depends(get_db),
    student:    User         = Depends(get_active_student),
) -> dict:
    """
    Returns all questions for the exam. is_correct is stripped
    from MCQ options so correct answers are not exposed.

    Verifies the attempt belongs to the authenticated student
    and is still in_progress.
    """
    # Verify ownership + status
    attempt_r = await db.execute(
        select(ExamAttempt).where(
            and_(
                ExamAttempt.id         == attempt_id,
                ExamAttempt.student_id == student.id,
            )
        )
    )
    attempt = attempt_r.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found.",
        )
    if attempt.status != AttemptStatus.in_progress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This attempt has already been submitted.",
        )

    questions = await get_exam_questions_for_student(
        db=db, exam_id=attempt.exam_id
    )

    # Also return existing saved answers so client can
    # restore state on page reload
    answers_r = await db.execute(
        select(Answer).where(
            Answer.attempt_id == attempt_id
        )
    )
    saved_answers = answers_r.scalars().all()
    saved_map = {
        a.question_id: {
            "selected_option_id": a.selected_option_id,
            "subjective_text":    a.subjective_text,
        }
        for a in saved_answers
    }

    # Attach saved answer to each question
    for q in questions:
        q["saved_answer"] = saved_map.get(q["id"])

    return {
        "attempt_id":  attempt_id,
        "exam_id":     attempt.exam_id,
        "items":       questions,
        "total":       len(questions),
    }


# ── POST /api/student/attempts/{attempt_id}/answers ───────────────

@router.post(
    "/attempts/{attempt_id}/answers",
    summary="Save or update an answer for one question.",
)
async def save_student_answer(
    attempt_id:         int,
    question_id:        int  = Query(...),
    selected_option_id: Optional[int] = Query(
        None,
        description="MCQ: option ID selected by student"
    ),
    subjective_text:    Optional[str] = Query(
        None,
        description="Subjective: student's answer text"
    ),
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> dict:
    """
    Saves or updates a single answer. Called on every question
    navigation so progress is preserved on refresh.

    Either selected_option_id (MCQ) or subjective_text
    (subjective) should be provided, not both.

    Returns immediately — answer persisted in DB.
    """
    ok, msg = await save_answer(
        db=db,
        attempt_id=attempt_id,
        question_id=question_id,
        selected_option_id=selected_option_id,
        subjective_text=subjective_text,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    return {"message": msg}


# ── POST /api/student/attempts/{attempt_id}/submit ────────────────

@router.post(
    "/attempts/{attempt_id}/submit",
    summary="Submit a completed exam attempt.",
)
async def submit_exam_attempt(
    attempt_id:  int,
    auto_submit: bool = Query(
        default=False,
        description="True when timer expired (client signals)"
    ),
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> dict:
    """
    Submits the attempt and triggers MCQ auto-grading.

    Can be called by:
      - Student clicking "Submit" button (auto_submit=false)
      - Client-side timer expiry (auto_submit=true)

    After submission:
      - MCQ answers are graded with negative marking applied.
      - ExamResult row is created/updated with computed marks.
      - Result is NOT visible to student until teacher
        calls publish-results.

    Returns summary of the submission.
    """
    ok, msg = await submit_attempt(
        db=db,
        attempt_id=attempt_id,
        student_id=student.id,
        auto_submit=auto_submit,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    return {"message": msg, "attempt_id": attempt_id}


# ── GET /api/student/attempts/{attempt_id}/status ────────────────

@router.get(
    "/attempts/{attempt_id}/status",
    summary="Get attempt progress summary.",
)
async def get_attempt_progress(
    attempt_id: int,
    db:         AsyncSession = Depends(get_db),
    student:    User         = Depends(get_active_student),
) -> dict:
    """
    Returns a lightweight progress summary for an attempt.
    Used by exam.js to show answered/unanswered counts and
    verify submission status after auto-submit.
    """
    summary = await get_attempt_status(
        db=db,
        attempt_id=attempt_id,
        student_id=student.id,
    )
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found.",
        )
    return summary


# ── POST /api/student/attempts/{attempt_id}/violations ───────────

@router.post(
    "/attempts/{attempt_id}/violations",
    summary="Log a proctor violation event.",
)
async def log_violation(
    attempt_id:     int,
    violation_type: str = Query(
        ...,
        description=(
            "One of: tab_switch, fullscreen_exit, "
            "camera_unavailable, copy_paste_attempt"
        ),
    ),
    details: Optional[str] = Query(None),
    db:      AsyncSession = Depends(get_db),
    student: User         = Depends(get_active_student),
) -> dict:
    """
    Records a proctoring violation event.
    Called by proctor.js on every detected violation.
    Silently succeeds even on partial failure.

    Verifies attempt belongs to student before logging.
    """
    # Validate violation_type
    valid_types = {
        "tab_switch", "fullscreen_exit",
        "camera_unavailable", "copy_paste_attempt",
    }
    if violation_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid violation_type. "
                f"Must be one of: {', '.join(valid_types)}"
            ),
        )

    # Verify attempt ownership
    attempt_r = await db.execute(
        select(ExamAttempt).where(
            and_(
                ExamAttempt.id         == attempt_id,
                ExamAttempt.student_id == student.id,
            )
        )
    )
    if attempt_r.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found.",
        )

    await log_proctor_violation(
        db=db,
        attempt_id=attempt_id,
        violation_type=violation_type,
        details=details,
    )
    return {"logged": True}


# ── POST /api/student/attempts/{attempt_id}/snapshots ────────────

@router.post(
    "/attempts/{attempt_id}/snapshots",
    summary="Upload a proctoring camera snapshot to GCS.",
)
async def upload_snapshot(
    attempt_id: int,
    request:    Request,
    db:         AsyncSession = Depends(get_db),
    student:    User         = Depends(get_active_student),
) -> dict:
    """
    Receives a base64-encoded JPEG snapshot from proctor.js
    and stores it in GCS.

    Request body: {"image_b64": "<base64 string>"}

    GCS path: snapshots/{exam_id}/{attempt_id}/{timestamp}.jpg

    Stores only the GCS path in proctor_snapshots — never
    a signed URL (those are generated at read time).
    """
    from models import ProctorSnapshot
    from core.gcs import upload_file
    from core.config import settings
    import base64

    # Verify attempt ownership
    attempt_r = await db.execute(
        select(ExamAttempt).where(
            and_(
                ExamAttempt.id         == attempt_id,
                ExamAttempt.student_id == student.id,
            )
        )
    )
    attempt = attempt_r.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found.",
        )

    body = await request.json()
    image_b64 = body.get("image_b64", "")
    if not image_b64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_b64 is required.",
        )

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data.",
        )

    now       = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
    gcs_path  = (
        f"snapshots/{attempt.exam_id}"
        f"/{attempt_id}/{timestamp}.jpg"
    )

    try:
        await upload_file(
            bucket=settings.GCS_BUCKET_NAME,
            destination_path=gcs_path,
            file_bytes=image_bytes,
            content_type="image/jpeg",
        )
    except Exception as e:
        # Don't block exam for snapshot failures
        return {"stored": False, "reason": str(e)}

    snapshot = ProctorSnapshot(
        attempt_id=attempt_id,
        gcs_path=gcs_path,
    )
    db.add(snapshot)
    await db.flush()

    return {"stored": True, "gcs_path": gcs_path}


# ── Shared IP helper ──────────────────────────────────────────────

def _get_ip(request: Request) -> str:
    if request is None:
        return "unknown"
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
