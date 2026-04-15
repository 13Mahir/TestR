"""
routers/admin.py
Admin panel API endpoints.
All routes prefixed with /api/admin in main.py.
This file will be extended in Prompts 10, 13, 14, 16, 18, 19.

This prompt implements: user management endpoints only.
"""

import csv
import io
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Request,
    UploadFile, File, Form, Query, status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_active_admin
from models import User, UserRole, SystemLogEventType, Exam, ExamAttempt, CourseEnrollment

from services.course_service import (
    create_course, list_courses, get_course_by_id,
    set_course_active, enroll_student_single,
    unenroll_student_single, enroll_students_bulk,
    assign_teacher_single, unassign_teacher_single,
    assign_teachers_bulk_csv, get_course_enrollments,
    get_course_assignments,
)
from schemas.admin import (
    CourseCreateRequest, CourseOut, CourseListResponse,
    EnrollSingleRequest, EnrollBulkRequest,
    AssignSingleRequest, EnrollmentOut,
)

from schemas.admin import (
    SingleUserCreateRequest,
    BulkStudentCreateRequest,
    BulkDeactivateRequest,
    UserOut,
    UserListResponse,
    BulkCreateResult,
    BulkDeactivateResult,
    BulkActivateResult,
)
from services.user_service import (
    create_single_user,
    bulk_create_students,
    bulk_create_teachers_from_csv,
    bulk_deactivate_students,
    bulk_activate_students,
    list_users,
    toggle_user_active,
)
from services.log_service import write_system_log, write_audit_log
from utils.pagination import get_pagination_params, PaginationParams

from fastapi.responses import StreamingResponse
import io
from datetime import datetime, timezone
from services.user_service import (
    generate_password_reset_token,
    consume_password_reset_token,
    get_active_reset_token,
)
from services.log_service import (
    list_system_logs,
    list_audit_logs,
    export_audit_logs_csv,
)


from services.school_service import (
    list_schools_with_branches,
    create_school,
    create_branch,
)
from schemas.admin import (
    PasswordResetTokenOut,
    ResetPasswordRequest,
    SystemLogOut,
    SystemLogListResponse,
    AuditLogOut,
    AuditLogListResponse,
    SchoolWithBranchesOut,
    BranchOut,
    SchoolCreateRequest,
    BranchCreateRequest,
)
from models import SystemLog, AuditLog

router = APIRouter(tags=["admin"])


# ── GET /api/admin/schools ───────────────────────────────────────────────────

@router.get(
    "/schools",
    response_model=list[SchoolWithBranchesOut],
    summary="List all schools with their associated branches.",
)
async def get_schools_and_branches(
    db:    AsyncSession = Depends(get_db),
    admin: User         = Depends(get_active_admin),
) -> list[SchoolWithBranchesOut]:
    """
    Returns a nested list of all schools and their branches.
    Admin only.
    """
    schools = await list_schools_with_branches(db)
    return [SchoolWithBranchesOut.model_validate(s) for s in schools]


# ── POST /api/admin/schools ──────────────────────────────────────────────────

@router.post(
    "/schools",
    response_model=SchoolWithBranchesOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new school.",
)
async def create_new_school(
    body:    SchoolCreateRequest,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> SchoolWithBranchesOut:
    """Creates a new school. Admin only."""
    ip = _get_ip(request)
    school = await create_school(db=db, code=body.code, name=body.name)
    
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="CREATE_SCHOOL",
        target_type="school",
        target_id=str(school.id),
        ip_address=ip,
        details={"code": body.code, "name": body.name},
    )
    await db.commit()
    # Eager load empty branches for response
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from models import School
    stmt = select(School).options(selectinload(School.branches)).where(School.id == school.id)
    school = (await db.execute(stmt)).scalar_one()
    return SchoolWithBranchesOut.model_validate(school)


# ── POST /api/admin/branches ─────────────────────────────────────────────────

@router.post(
    "/branches",
    response_model=BranchOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new branch for a school.",
)
async def create_new_branch(
    body:    BranchCreateRequest,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> BranchOut:
    """Creates a new branch. Admin only."""
    ip = _get_ip(request)
    branch = await create_branch(
        db=db, school_id=body.school_id, code=body.code, name=body.name
    )
    
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="CREATE_BRANCH",
        target_type="branch",
        target_id=str(branch.id),
        ip_address=ip,
        details={"school_id": body.school_id, "code": body.code, "name": body.name},
    )
    await db.commit()
    return BranchOut.model_validate(branch)



def _get_ip(request: Request) -> str:
    """Extracts client IP. Checks X-Forwarded-For for Cloud Run."""
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── GET /api/admin/users ──────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users with optional filters and pagination.",
)
async def list_all_users(
    role:      Optional[str]  = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by status"),
    search:    Optional[str]  = Query(None, description="Search email/name"),
    params:    PaginationParams = Depends(get_pagination_params),
    db:        AsyncSession     = Depends(get_db),
    admin:     User             = Depends(get_active_admin),
) -> UserListResponse:
    """
    Returns paginated users. Admin only.
    Supports filtering by role, active status, and text search.
    """
    users, total = await list_users(
        db=db,
        role=role,
        is_active=is_active,
        search=search,
        limit=params.limit,
        offset=params.offset,
    )

    total_pages = max(1, -(-total // params.page_size))

    return UserListResponse(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_prev=params.page > 1,
    )


# ── POST /api/admin/users/single ─────────────────────────────────────────────

@router.post(
    "/users/single",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a single user (any role) by email.",
)
async def create_user_single(
    body:    SingleUserCreateRequest,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> UserOut:
    """
    Creates a single user. Role is derived from email pattern:
      - YYBRHRLN@sch.clg.ac.in → student
      - first.last@clg.ac.in   → teacher
      - admin@clg.ac.in        → admin (only one admin allowed)

    All new users have force_password_reset=True.

    Writes:
      - system_logs row with event_type='users_created'
      - audit_logs row with action='CREATE_USER'
    """
    ip = _get_ip(request)

    user = await create_single_user(
        db=db,
        email=body.email,
        password=body.password,
        created_by_id=admin.id,
    )

    # Notification
    from services.notification_service import create_notification
    await create_notification(
        db=db,
        user_id=user.id,
        type="ACCOUNT_CREATED",
        title="Welcome!",
        body=f"Your account as {user.role.value} has been created successfully. Please change your password on first login.",
        link="/auth/change-password"
    )

    # System log
    await write_system_log(
        db=db,
        event_type=SystemLogEventType.users_created,
        actor_id=admin.id,
        description=f"Single user created: {user.email} ({user.role.value})",
        metadata={"email": user.email, "role": user.role.value, "user_id": user.id},
    )

    # Audit log
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="CREATE_USER",
        target_type="user",
        target_id=str(user.id),
        ip_address=ip,
        details={"email": user.email, "role": user.role.value},
    )

    await db.commit()
    return UserOut.model_validate(user)


# ── POST /api/admin/users/bulk-students ──────────────────────────────────────

@router.post(
    "/users/bulk-students",
    response_model=BulkCreateResult,
    status_code=status.HTTP_200_OK,
    summary="Bulk create students for a batch + branch + roll range.",
)
async def bulk_create_students_endpoint(
    body:    BulkStudentCreateRequest,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> BulkCreateResult:
    """
    Creates student accounts for every roll number in the range
    [roll_start, roll_end] inclusive for the given batch and branch.

    Email format: {batch}{branch}{roll:03d}@{school}.clg.ac.in

    Bulk creation fires ONE system_log entry and ONE audit_log entry
    regardless of how many students are created.

    Returns a summary of created, skipped, and failed accounts.
    """
    ip = _get_ip(request)

    created, skipped, failed, errors, created_ids = await bulk_create_students(
        db=db,
        batch_year=body.batch_year,
        branch_code=body.branch_code,
        roll_start=body.roll_start,
        roll_end=body.roll_end,
        default_password=body.default_password,
        created_by_id=admin.id,
    )

    total_attempted = body.roll_end - body.roll_start + 1

    # System log — one entry for the whole bulk operation
    if created > 0:
        await write_system_log(
            db=db,
            event_type=SystemLogEventType.users_created,
            actor_id=admin.id,
            description=(
                f"Bulk student creation: {created} created, "
                f"{skipped} skipped, {failed} failed. "
                f"Batch {body.batch_year} Branch {body.branch_code} "
                f"Rolls {body.roll_start:03d}-{body.roll_end:03d}."
            ),
            metadata={
                "batch_year":  body.batch_year,
                "branch_code": body.branch_code,
                "roll_start":  body.roll_start,
                "roll_end":    body.roll_end,
                "created":     created,
                "skipped":     skipped,
                "failed":      failed,
            },
        )

    # Bulk Notification
    if created_ids:
        from services.notification_service import create_notifications_bulk
        await create_notifications_bulk(
            db=db,
            user_ids=created_ids,
            type="ACCOUNT_CREATED",
            title="Welcome to ExamPortal!",
            body=f"Your student account for batch {body.batch_year} has been created. Please change your password on first login.",
            link="/auth/change-password"
        )

    # Audit log — one entry for the whole bulk operation
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="BULK_CREATE_STUDENTS",
        target_type="user",
        target_id=None,
        ip_address=ip,
        details={
            "batch_year":  body.batch_year,
            "branch_code": body.branch_code,
            "roll_start":  body.roll_start,
            "roll_end":    body.roll_end,
            "created":     created,
            "skipped":     skipped,
            "failed":      failed,
        },
    )

    message = (
        f"Bulk student creation complete: {created} created, "
        f"{skipped} already existed (skipped), {failed} failed "
        f"out of {total_attempted} attempted."
    )

    await db.commit()

    return BulkCreateResult(
        created=created,
        skipped=skipped,
        failed=failed,
        errors=errors[:20],  # Cap error list to 20 items in response
        message=message,
    )


# ── POST /api/admin/users/bulk-teachers ──────────────────────────────────────

@router.post(
    "/users/bulk-teachers",
    response_model=BulkCreateResult,
    status_code=status.HTTP_200_OK,
    summary="Bulk create teachers from a CSV file.",
)
async def bulk_create_teachers_endpoint(
    request:          Request,
    default_password: str        = Form(...),
    csv_file:         UploadFile = File(
        ...,
        description="CSV file with columns: first_name, last_name"
    ),
    db:    AsyncSession = Depends(get_db),
    admin: User         = Depends(get_active_admin),
) -> BulkCreateResult:
    """
    Creates teacher accounts from a CSV upload.

    CSV format (header row required):
        first_name,last_name
        John,Smith
        Jane,Doe

    Generates email as first.last@clg.ac.in
    Max 500 rows per upload.

    Writes ONE system_log and ONE audit_log entry for the entire
    batch regardless of row count.
    """
    ip = _get_ip(request)

    # Validate file type
    if csv_file.content_type not in (
        "text/csv",
        "text/plain",
        "application/csv",
        "application/vnd.ms-excel",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV. Received: "
                   f"{csv_file.content_type}",
        )

    # Validate default_password length
    if len(default_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="default_password must be at least 8 characters.",
        )

    # Read file bytes
    csv_bytes = await csv_file.read()
    if len(csv_bytes) > 1_000_000:  # 1MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file too large. Maximum size is 1MB.",
        )

    created, skipped, failed, errors, created_ids = await bulk_create_teachers_from_csv(
        db=db,
        csv_bytes=csv_bytes,
        default_password=default_password,
        created_by_id=admin.id,
    )

    # System log — one entry for the whole bulk operation
    if created > 0:
        await write_system_log(
            db=db,
            event_type=SystemLogEventType.users_created,
            actor_id=admin.id,
            description=(
                f"Bulk teacher creation from CSV: {created} created, "
                f"{skipped} skipped, {failed} failed."
            ),
            metadata={
                "created": created,
                "skipped": skipped,
                "failed":  failed,
                "filename": csv_file.filename,
            },
        )

    # Bulk Notification
    if created_ids:
        from services.notification_service import create_notifications_bulk
        await create_notifications_bulk(
            db=db,
            user_ids=created_ids,
            type="ACCOUNT_CREATED",
            title="Welcome to ExamPortal!",
            body="Your teacher account has been created. Please change your password on first login.",
            link="/auth/change-password"
        )

    # Audit log
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="BULK_CREATE_TEACHERS",
        target_type="user",
        target_id=None,
        ip_address=ip,
        details={
            "created":  created,
            "skipped":  skipped,
            "failed":   failed,
            "filename": csv_file.filename,
        },
    )

    message = (
        f"Bulk teacher creation complete: {created} created, "
        f"{skipped} already existed (skipped), {failed} failed."
    )

    await db.commit()

    return BulkCreateResult(
        created=created,
        skipped=skipped,
        failed=failed,
        errors=errors[:20],
        message=message,
    )


# ── POST /api/admin/users/bulk-deactivate ────────────────────────────────────

@router.post(
    "/users/bulk-deactivate",
    response_model=BulkDeactivateResult,
    summary="Deactivate all students in a batch (optionally by branch).",
)
async def bulk_deactivate_endpoint(
    body:    BulkDeactivateRequest,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> BulkDeactivateResult:
    """
    Deactivates student accounts for an entire batch year.
    Optionally filter by branch_code to deactivate one branch only.
    Immediately invalidates their active sessions.

    Writes ONE audit_log entry.
    """
    ip = _get_ip(request)

    count = await bulk_deactivate_students(
        db=db,
        batch_year=body.batch_year,
        branch_code=body.branch_code,
    )

    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No active students found for batch '{body.batch_year}'"
                + (f" branch '{body.branch_code}'" if body.branch_code else "")
                + "."
            ),
        )

    # Audit log
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="BULK_DEACTIVATE",
        target_type="user",
        target_id=None,
        ip_address=ip,
        details={
            "batch_year":  body.batch_year,
            "branch_code": body.branch_code,
            "deactivated": count,
        },
    )

    scope = (
        f"batch {body.batch_year}"
        + (f" branch {body.branch_code}" if body.branch_code else
           " (all branches)")
    )

    await db.commit()

    return BulkDeactivateResult(
        deactivated=count,
        message=f"Deactivated {count} student account(s) for {scope}.",
    )


# ── POST /api/admin/users/bulk-activate ──────────────────────────────────────

@router.post(
    "/users/bulk-activate",
    response_model=BulkActivateResult,
    summary="Activate all inactive students in a batch (optionally by branch).",
)
async def bulk_activate_endpoint(
    body:    BulkDeactivateRequest,   # same fields: batch_year + branch_code
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> BulkActivateResult:
    """
    Activates (re-enables) student accounts for a batch year.
    Optionally filter by branch_code.
    Only targets currently-inactive students.
    """
    ip = _get_ip(request)

    count = await bulk_activate_students(
        db=db,
        batch_year=body.batch_year,
        branch_code=body.branch_code,
    )

    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No inactive students found for batch '{body.batch_year}'"
                + (f" branch '{body.branch_code}'" if body.branch_code else "")
                + "."
            ),
        )

    # Audit log
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="BULK_ACTIVATE",
        target_type="user",
        target_id=None,
        ip_address=ip,
        details={
            "batch_year":  body.batch_year,
            "branch_code": body.branch_code,
            "activated":   count,
        },
    )

    scope = (
        f"batch {body.batch_year}"
        + (f" branch {body.branch_code}" if body.branch_code else
           " (all branches)")
    )

    await db.commit()

    return BulkActivateResult(
        activated=count,
        message=f"Activated {count} student account(s) for {scope}.",
    )



# ── POST /api/admin/users/{user_id}/force-reset ───────────────────────────────

@router.post(
    "/users/{user_id}/force-reset",
    response_model=PasswordResetTokenOut,
    summary="Generate a password reset token for a user.",
)
async def force_password_reset(
    user_id: int,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> PasswordResetTokenOut:
    """
    Generates a secure reset token for the target user and sets
    force_password_reset=True on their account.

    The token is returned in the response body — admin must
    share it manually with the user. No email is sent.

    The token:
      - Is 64 hex characters (cryptographically random)
      - Expires in 48 hours
      - Can only be used once
      - Is shown in the response and is not retrievable again
        (admin must generate a new one if lost)

    Also sets force_password_reset=True on the user record so
    that even if they are currently logged in they are blocked
    from accessing any page until password is changed.

    Writes an audit_log entry with action='FORCE_PASSWORD_RESET'.
    """
    ip = _get_ip(request)

    # Generate token
    token_row, error = await generate_password_reset_token(
        db=db,
        target_user_id=user_id,
        admin_id=admin.id,
    )
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    # Set force_password_reset flag on the user
    from sqlalchemy import update as sa_update, select
    await db.execute(
        sa_update(User)
        .where(User.id == user_id)
        .values(force_password_reset=True)
    )
    await db.flush()

    # Load user for response
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    target_user = user_result.scalar_one()

    # Audit log
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="FORCE_PASSWORD_RESET",
        target_type="user",
        target_id=str(user_id),
        ip_address=ip,
        details={
            "email":      target_user.email,
            "expires_at": token_row.expires_at.isoformat(),
        },
    )

    await db.commit()

    return PasswordResetTokenOut(
        user_id=user_id,
        user_email=target_user.email,
        token=token_row.token,
        expires_at=token_row.expires_at,
        message=(
            "Token generated. Share this token with the user. "
            "It expires in 48 hours and can only be used once. "
            "It will not be shown again."
        ),
    )


# ── POST /api/admin/users/consume-reset-token ─────────────────────────────────

@router.post(
    "/users/consume-reset-token",
    summary="Apply a password reset token (used by the reset page).",
)
async def consume_reset_token(
    body:         ResetPasswordRequest,
    db:           AsyncSession = Depends(get_db),
) -> dict:
    """
    Public endpoint — no auth required.
    Validates and consumes a password reset token, applying the
    new password to the user account.

    Called by the password reset page when user submits their new
    password using the token the admin shared with them.
    """
    success, message = await consume_password_reset_token(
        db=db,
        raw_token=body.token,
        new_password=body.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    await db.commit()

    return {"message": message}


# ── GET /api/admin/users/{user_id}/reset-token-status ────────────────────────

@router.get(
    "/users/{user_id}/reset-token-status",
    summary="Check if a pending reset token exists for a user.",
)
async def get_reset_token_status(
    user_id: int,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> dict:
    """
    Returns whether a valid (unused, unexpired) reset token exists
    for the target user. Used by the admin panel to show a
    "Token pending" indicator.

    Returns:
        {"has_pending_token": bool, "expires_at": str | null}

    Note: The actual token string is NOT returned here — it was only
    shown once at generation time.
    """
    token_row = await get_active_reset_token(
        db=db,
        target_user_id=user_id,
    )

    if token_row is None:
        return {"has_pending_token": False, "expires_at": None}

    return {
        "has_pending_token": True,
        "expires_at": token_row.expires_at.isoformat(),
    }


# ── GET /api/admin/logs/system ────────────────────────────────────────────────

@router.get(
    "/logs/system",
    response_model=SystemLogListResponse,
    summary="List system logs with optional filters.",
)
async def get_system_logs(
    event_type: Optional[str] = Query(
        None,
        description=(
            "Filter by event type. One of: exam_created, exam_published, "
            "results_published, users_created, course_created, "
            "course_activated, course_deactivated"
        ),
    ),
    actor_id: Optional[int] = Query(
        None, description="Filter by actor user ID"
    ),
    params: PaginationParams = Depends(get_pagination_params),
    db:     AsyncSession     = Depends(get_db),
    admin:  User             = Depends(get_active_admin),
) -> SystemLogListResponse:
    """
    Returns paginated system logs, newest first.
    Admin only.
    """
    logs, total = await list_system_logs(
        db=db,
        event_type=event_type,
        actor_id=actor_id,
        limit=params.limit,
        offset=params.offset,
    )

    total_pages = max(1, -(-total // params.page_size))

    return SystemLogListResponse(
        items=[SystemLogOut.model_validate(l) for l in logs],
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_prev=params.page > 1,
    )


# ── GET /api/admin/logs/audit ─────────────────────────────────────────────────

@router.get(
    "/logs/audit",
    response_model=AuditLogListResponse,
    summary="List audit logs with optional filters.",
)
async def get_audit_logs(
    action:      Optional[str] = Query(None, description="Filter by action"),
    admin_id:    Optional[int] = Query(None, description="Filter by admin ID"),
    target_type: Optional[str] = Query(
        None, description="Filter by target type: user, course, exam"
    ),
    params: PaginationParams = Depends(get_pagination_params),
    db:     AsyncSession     = Depends(get_db),
    admin:  User             = Depends(get_active_admin),
) -> AuditLogListResponse:
    """
    Returns paginated audit logs, newest first.
    Admin only.
    """
    logs, total = await list_audit_logs(
        db=db,
        action=action,
        admin_id=admin_id,
        target_type=target_type,
        limit=params.limit,
        offset=params.offset,
    )

    total_pages = max(1, -(-total // params.page_size))

    return AuditLogListResponse(
        items=[AuditLogOut.model_validate(l) for l in logs],
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_prev=params.page > 1,
    )


# ── GET /api/admin/logs/audit/export ─────────────────────────────────────────

@router.get(
    "/logs/audit/export",
    summary="Export all audit logs as a downloadable CSV file.",
)
async def export_audit_logs(
    action:      Optional[str] = Query(None),
    admin_id:    Optional[int] = Query(None),
    target_type: Optional[str] = Query(None),
    db:    AsyncSession = Depends(get_db),
    admin: User         = Depends(get_active_admin),
) -> StreamingResponse:
    """
    Exports audit logs as a CSV file download.
    Applies the same filters as GET /api/admin/logs/audit but
    returns ALL matching rows (no pagination) as a file attachment.

    The filename includes the current UTC date:
        audit_log_YYYY-MM-DD.csv
    """
    csv_content = await export_audit_logs_csv(
        db=db,
        action=action,
        admin_id=admin_id,
        target_type=target_type,
    )

    # Build filename with current date
    today     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename  = f"audit_log_{today}.csv"

    return StreamingResponse(
        content=io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )

@router.get("/debug-db")
async def debug_db(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    try:
        res = await db.execute(text("DESCRIBE system_logs"))
        cols = [r[0] for r in res.fetchall()]
        return {"cols": cols}
    except Exception as e:
        return {"error": str(e)}


# ── POST /api/admin/courses ───────────────────────────────────────────────────

@router.post(
    "/courses",
    response_model=CourseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course.",
)
async def create_course_endpoint(
    body:    CourseCreateRequest,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> CourseOut:
    """
    Creates a new course.
    course_code must be unique and match format YYBRNNNM.
    branch_code must exist in branches table.

    Writes:
      - system_logs: event_type='course_created'
      - audit_logs:  action='CREATE_COURSE'
    """
    ip = _get_ip(request)

    course = await create_course(
        db=db,
        course_code=body.course_code,
        name=body.name,
        description=body.description,
        branch_code=body.branch_code,
        year=body.year,
        mode=body.mode,
        created_by_id=admin.id,
    )

    # Capture ORM attributes as plain values before further DB ops
    # expire the session state (MissingGreenlet prevention)
    c_id          = course.id
    c_code        = course.course_code
    c_name        = course.name
    c_description = course.description
    c_year        = course.year
    c_mode_value  = course.mode.value
    c_is_active   = course.is_active
    c_created_at  = course.created_at

    await write_system_log(
        db=db,
        event_type=SystemLogEventType.course_created,
        actor_id=admin.id,
        description=(
            f"Course created: {c_code} — {c_name}"
        ),
        metadata={
            "course_id":   c_id,
            "course_code": c_code,
            "branch_code": body.branch_code,
        },
    )

    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="CREATE_COURSE",
        target_type="course",
        target_id=c_id,
        ip_address=ip,
        details={
            "course_code": c_code,
            "name":        c_name,
            "branch_code": body.branch_code,
            "mode":        body.mode,
        },
    )

    await db.commit()

    return CourseOut(
        id=c_id,
        course_code=c_code,
        name=c_name,
        description=c_description,
        branch_code=body.branch_code,
        year=c_year,
        mode=c_mode_value,
        is_active=c_is_active,
        created_at=c_created_at,
        enrolled_students=0,
        assigned_teachers=0,
    )


# ── GET /api/admin/courses ────────────────────────────────────────────────────

@router.get(
    "/courses",
    response_model=CourseListResponse,
    summary="List all courses with optional filters.",
)
async def list_courses_endpoint(
    is_active:   Optional[bool] = Query(None),
    branch_code: Optional[str]  = Query(None),
    search:      Optional[str]  = Query(None),
    params:      PaginationParams = Depends(get_pagination_params),
    db:          AsyncSession     = Depends(get_db),
    admin:       User             = Depends(get_active_admin),
) -> CourseListResponse:
    """
    Returns paginated courses with enrollment + assignment counts.
    Admin only.
    """
    courses, total = await list_courses(
        db=db,
        is_active=is_active,
        branch_code=branch_code,
        search=search,
        limit=params.limit,
        offset=params.offset,
    )

    total_pages = max(1, -(-total // params.page_size))

    return CourseListResponse(
        items=[CourseOut(**c) for c in courses],
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_prev=params.page > 1,
    )


# ── GET /api/admin/courses/{course_id} ───────────────────────────────────────

@router.get(
    "/courses/{course_id}",
    response_model=CourseOut,
    summary="Get a single course by ID.",
)
async def get_course_endpoint(
    course_id: int,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> CourseOut:
    """Returns a single course with enrollment + assignment counts."""
    course = await get_course_by_id(db=db, course_id=course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found.",
        )
    return CourseOut(**course)


# ── POST /api/admin/courses/{course_id}/activate ──────────────────────────────

@router.post(
    "/courses/{course_id}/activate",
    summary="Activate a course.",
)
async def activate_course(
    course_id: int,
    request:   Request,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> dict:
    """
    Sets course.is_active = True.
    Writes system_log + audit_log.
    """
    ip = _get_ip(request)

    await set_course_active(
        db=db, course_id=course_id, is_active=True
    )

    await write_system_log(
        db=db,
        event_type=SystemLogEventType.course_activated,
        actor_id=admin.id,
        description=f"Course {course_id} activated.",
        metadata={"course_id": course_id},
    )
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="ACTIVATE_COURSE",
        target_type="course",
        target_id=course_id,
        ip_address=ip,
    )

    await db.commit()

    return {"message": msg}


# ── POST /api/admin/courses/{course_id}/deactivate ────────────────────────────

@router.post(
    "/courses/{course_id}/deactivate",
    summary="Deactivate a course.",
)
async def deactivate_course(
    course_id: int,
    request:   Request,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> dict:
    """
    Sets course.is_active = False.
    Writes system_log + audit_log.
    """
    ip = _get_ip(request)

    await set_course_active(
        db=db, course_id=course_id, is_active=False
    )

    await write_system_log(
        db=db,
        event_type=SystemLogEventType.course_deactivated,
        actor_id=admin.id,
        description=f"Course {course_id} deactivated.",
        metadata={"course_id": course_id},
    )
    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="DEACTIVATE_COURSE",
        target_type="course",
        target_id=course_id,
        ip_address=ip,
    )

    await db.commit()

    return {"message": msg}


# ── GET /api/admin/courses/{course_id}/enrollments ───────────────────────────

@router.get(
    "/courses/{course_id}/enrollments",
    summary="List students enrolled in a course.",
)
async def list_enrollments(
    course_id: int,
    params:    PaginationParams = Depends(get_pagination_params),
    db:        AsyncSession     = Depends(get_db),
    admin:     User             = Depends(get_active_admin),
) -> dict:
    """Returns paginated list of enrolled students for a course."""
    items, total = await get_course_enrollments(
        db=db,
        course_id=course_id,
        limit=params.limit,
        offset=params.offset,
    )
    total_pages = max(1, -(-total // params.page_size))
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": total_pages,
    }


# ── POST /api/admin/courses/{course_id}/enroll/single ────────────────────────

@router.post(
    "/courses/{course_id}/enroll/single",
    response_model=EnrollmentOut,
    summary="Enroll a single student into a course by email.",
)
async def enroll_single(
    course_id: int,
    body:      EnrollSingleRequest,
    request:   Request,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> EnrollmentOut:
    """
    Enrolls one student by email.
    Writes audit_log: action='ENROLL_STUDENT'.
    """
    ip = _get_ip(request)

    await enroll_student_single(
        db=db,
        course_id=course_id,
        student_email=body.student_email,
        enrolled_by_id=admin.id,
    )

    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="ENROLL_STUDENT",
        target_type="enrollment",
        ip_address=ip,
        details={
            "course_id":     course_id,
            "student_email": body.student_email,
        },
    )

    return EnrollmentOut(enrolled=1, message=f"Student '{body.student_email}' enrolled successfully.")


# ── POST /api/admin/courses/{course_id}/unenroll/single ──────────────────────

@router.post(
    "/courses/{course_id}/unenroll/single",
    response_model=EnrollmentOut,
    summary="Remove a single student from a course by email.",
)
async def unenroll_single(
    course_id: int,
    body:      EnrollSingleRequest,
    request:   Request,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> EnrollmentOut:
    """
    Unenrolls one student by email.
    Writes audit_log: action='UNENROLL_STUDENT'.
    """
    ip = _get_ip(request)

    await unenroll_student_single(
        db=db,
        course_id=course_id,
        student_email=body.student_email,
    )

    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="UNENROLL_STUDENT",
        target_type="enrollment",
        ip_address=ip,
        details={
            "course_id":     course_id,
            "student_email": body.student_email,
        },
    )

    return EnrollmentOut(unenrolled=1, message=f"Student '{body.student_email}' unenrolled successfully.")


# ── POST /api/admin/courses/{course_id}/enroll/bulk ──────────────────────────

@router.post(
    "/courses/{course_id}/enroll/bulk",
    response_model=EnrollmentOut,
    summary="Bulk enroll students by batch + branch + roll range.",
)
async def enroll_bulk(
    course_id: int,
    body:      EnrollBulkRequest,
    request:   Request,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> EnrollmentOut:
    """
    Enrolls all students matching batch+branch+roll range.
    Writes ONE audit_log entry for the entire operation.
    """
    ip = _get_ip(request)

    enrolled, skipped, failed, errors = await enroll_students_bulk(
        db=db,
        course_id=course_id,
        batch_year=body.batch_year,
        branch_code=body.branch_code,
        roll_start=body.roll_start,
        roll_end=body.roll_end,
        enrolled_by_id=admin.id,
    )

    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="BULK_ENROLL_STUDENTS",
        target_type="enrollment",
        ip_address=ip,
        details={
            "course_id":   course_id,
            "batch_year":  body.batch_year,
            "branch_code": body.branch_code,
            "roll_start":  body.roll_start,
            "roll_end":    body.roll_end,
            "enrolled":    enrolled,
            "skipped":     skipped,
            "failed":      failed,
        },
    )

    message = (
        f"Bulk enrollment complete: {enrolled} enrolled, "
        f"{skipped} skipped (already enrolled or inactive), "
        f"{failed} failed."
    )

    await db.commit()

    return EnrollmentOut(
        enrolled=enrolled,
        skipped=skipped,
        failed=failed,
        errors=errors[:20],
        message=message,
    )


# ── GET /api/admin/courses/{course_id}/assignments ───────────────────────────

@router.get(
    "/courses/{course_id}/assignments",
    summary="List teachers assigned to a course.",
)
async def list_assignments(
    course_id: int,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> dict:
    """Returns all teachers assigned to a course (not paginated)."""
    items = await get_course_assignments(
        db=db, course_id=course_id
    )
    return {"items": items, "total": len(items)}


# ── POST /api/admin/courses/{course_id}/assign/single ────────────────────────

@router.post(
    "/courses/{course_id}/assign/single",
    response_model=EnrollmentOut,
    summary="Assign a single teacher to a course by email.",
)
async def assign_single(
    course_id: int,
    body:      AssignSingleRequest,
    request:   Request,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> EnrollmentOut:
    """
    Assigns one teacher by email.
    Writes audit_log: action='ASSIGN_TEACHER'.
    """
    ip = _get_ip(request)

    teacher_id = await assign_teacher_single(
        db=db,
        course_id=course_id,
        teacher_email=body.teacher_email,
        assigned_by_id=admin.id,
    )

    # Notify teacher
    if teacher_id:
        from services.notification_service import create_notification
        from services.course_service import get_course_by_id
        course_data = await get_course_by_id(db, course_id)
        course_name = course_data["name"] if course_data else "a course"
        await create_notification(
            db=db,
            user_id=t_id,
            type="COURSE_ASSIGNMENT",
            title="New Course Assigned",
            body=f"You have been assigned to teach: {course_name}",
            link=f"/teacher/courses"
        )

    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="ASSIGN_TEACHER",
        target_type="assignment",
        ip_address=ip,
        details={
            "course_id":     course_id,
            "teacher_email": body.teacher_email,
        },
    )

    await db.commit()

    return EnrollmentOut(assigned=1, message=msg)


# ── POST /api/admin/courses/{course_id}/unassign/single ──────────────────────

@router.post(
    "/courses/{course_id}/unassign/single",
    response_model=EnrollmentOut,
    summary="Remove a teacher assignment from a course by email.",
)
async def unassign_single(
    course_id: int,
    body:      AssignSingleRequest,
    request:   Request,
    db:        AsyncSession = Depends(get_db),
    admin:     User         = Depends(get_active_admin),
) -> EnrollmentOut:
    """
    Unassigns one teacher by email.
    Writes audit_log: action='UNASSIGN_TEACHER'.
    """
    ip = _get_ip(request)

    await unassign_teacher_single(
        db=db,
        course_id=course_id,
        teacher_email=body.teacher_email,
    )

    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="UNASSIGN_TEACHER",
        target_type="assignment",
        ip_address=ip,
        details={
            "course_id":     course_id,
            "teacher_email": body.teacher_email,
        },
    )

    await db.commit()

    return EnrollmentOut(unassigned=1, message=f"Teacher '{body.teacher_email}' unassigned successfully.")


# ── POST /api/admin/courses/{course_id}/assign/bulk-csv ──────────────────────

@router.post(
    "/courses/{course_id}/assign/bulk-csv",
    response_model=EnrollmentOut,
    summary="Assign multiple teachers from a CSV file.",
)
async def assign_bulk_csv(
    course_id: int,
    request:   Request,
    csv_file:  UploadFile = File(
        ...,
        description="CSV with columns: first_name, last_name"
    ),
    db:    AsyncSession = Depends(get_db),
    admin: User         = Depends(get_active_admin),
) -> EnrollmentOut:
    """
    Assigns teachers from a CSV upload.
    Constructs email as first.last@clg.ac.in per row.
    Writes ONE audit_log entry for the entire operation.
    """
    ip = _get_ip(request)

    if csv_file.content_type not in (
        "text/csv", "text/plain",
        "application/csv", "application/vnd.ms-excel",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV.",
        )

    csv_bytes = await csv_file.read()
    if len(csv_bytes) > 500_000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file too large. Maximum size is 500KB.",
        )

    assigned, skipped, failed, errors, assigned_ids = await assign_teachers_bulk_csv(
        db=db,
        course_id=course_id,
        csv_bytes=csv_bytes,
        assigned_by_id=admin.id,
    )

    # Notify teachers bulk
    if assigned_ids:
        from services.notification_service import create_notifications_bulk
        from services.course_service import get_course_by_id
        course_data = await get_course_by_id(db, course_id)
        course_name = course_data["name"] if course_data else "a course"
        await create_notifications_bulk(
            db=db,
            user_ids=assigned_ids,
            type="COURSE_ASSIGNMENT",
            title="New Course Assigned",
            body=f"You have been assigned to teach: {course_name}",
            link=f"/teacher/courses"
        )

    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action="BULK_ASSIGN_TEACHERS",
        target_type="assignment",
        ip_address=ip,
        details={
            "course_id": course_id,
            "assigned":  assigned,
            "skipped":   skipped,
            "failed":    failed,
            "filename":  csv_file.filename,
        },
    )

    message = (
        f"Bulk teacher assignment complete: {assigned} assigned, "
        f"{skipped} skipped (already assigned), {failed} failed."
    )

    await db.commit()

    return EnrollmentOut(
        assigned=assigned,
        skipped=skipped,
        failed=failed,
        errors=errors[:20],
        message=message,
    )


# ── POST /api/admin/users/{user_id}/toggle-active ─────────────────────────────

@router.post(
    "/users/{user_id}/toggle-active",
    summary="Toggle a user's active status (activate ↔ deactivate).",
)
async def toggle_user_active_endpoint(
    user_id: int,
    request: Request,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_active_admin),
) -> dict:
    """
    Flips a user's is_active flag.  If deactivating, also invalidates
    their session so they are logged out immediately.

    Returns {"is_active": bool, "message": str}.
    """
    new_status, err = await toggle_user_active(
        db=db,
        target_user_id=user_id,
    )

    if err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err,
        )

    ip = _get_ip(request)
    action_word = "activated" if new_status else "deactivated"

    await write_audit_log(
        db=db,
        admin_id=admin.id,
        action=f"user_{action_word}",
        target_type="user",
        target_id=str(user_id),
        ip_address=ip,
        details={"new_is_active": new_status},
    )

    await write_system_log(
        db=db,
        event_type="users_created",
        actor_id=admin.id,
        description=f"Admin {action_word} user ID {user_id}.",
    )

    await db.commit()

    return {
        "is_active": new_status,
        "message": f"User {action_word} successfully.",
    }


# ── GET /api/admin/overview/stats ─────────────────────────────────

@router.get(
    "/overview/stats",
    summary="System-wide summary stats for admin dashboard.",
)
async def get_overview_stats(
    db:    AsyncSession = Depends(get_db),
    admin: User         = Depends(get_active_admin),
) -> dict:
    """
    Returns counts used by the admin overview dashboard.
    All counts are computed in a single async batch.

    Returns:
    {
      users: {
        total: int,
        students: int,
        teachers: int,
        active: int,
        inactive: int,
      },
      courses: {
        total: int,
        active: int,
        inactive: int,
      },
      exams: {
        total: int,
        published: int,
        results_published: int,
      },
      enrollments: {
        total: int,
      },
      recent_system_logs: [
        {id, event_type, description, created_at}
        ... last 5 entries
      ]
    }
    """
    from sqlalchemy import select, func
    from models import (
        User, UserRole, Course, SystemLog,
        Exam, CourseEnrollment,
    )

    # ── User counts ───────────────────────────────────────────────
    total_users_r = await db.execute(
        select(func.count(User.id))
    )
    total_users = total_users_r.scalar_one()

    students_r = await db.execute(
        select(func.count(User.id))
        .where(User.role == UserRole.student)
    )
    students = students_r.scalar_one()

    teachers_r = await db.execute(
        select(func.count(User.id))
        .where(User.role == UserRole.teacher)
    )
    teachers = teachers_r.scalar_one()

    active_r = await db.execute(
        select(func.count(User.id))
        .where(User.is_active == True)
    )
    active_users = active_r.scalar_one()

    # ── Course counts ─────────────────────────────────────────────
    total_courses_r = await db.execute(
        select(func.count(Course.id))
    )
    total_courses = total_courses_r.scalar_one()

    active_courses_r = await db.execute(
        select(func.count(Course.id))
        .where(Course.is_active == True)
    )
    active_courses = active_courses_r.scalar_one()

    # ── Exam counts ───────────────────────────────────────────────
    total_exams_r = await db.execute(
        select(func.count(Exam.id))
    )
    total_exams = total_exams_r.scalar_one()

    published_exams_r = await db.execute(
        select(func.count(Exam.id))
        .where(Exam.is_published == True)
    )
    published_exams = published_exams_r.scalar_one()

    results_published_r = await db.execute(
        select(func.count(Exam.id))
        .where(Exam.results_published == True)
    )
    results_published = results_published_r.scalar_one()

    # ── Enrollment count ──────────────────────────────────────────
    total_enroll_r = await db.execute(
        select(func.count(CourseEnrollment.id))
    )
    total_enrollments = total_enroll_r.scalar_one()

    # ── Recent system logs (last 5) ───────────────────────────────
    logs_r = await db.execute(
        select(SystemLog)
        .order_by(SystemLog.created_at.desc())
        .limit(5)
    )
    recent_logs = logs_r.scalars().all()

    return {
        "users": {
            "total":    total_users,
            "students": students,
            "teachers": teachers,
            "active":   active_users,
            "inactive": total_users - active_users,
        },
        "courses": {
            "total":    total_courses,
            "active":   active_courses,
            "inactive": total_courses - active_courses,
        },
        "exams": {
            "total":            total_exams,
            "published":        published_exams,
            "results_published": results_published,
        },
        "enrollments": {
            "total": total_enrollments,
        },
        "recent_system_logs": [
            {
                "id":          log.id,
                "event_type":  log.event_type.value if hasattr(log.event_type, "value") else log.event_type,
                "description": log.description,
                "created_at":  log.created_at.isoformat(),
            }
            for log in recent_logs
        ],
    }
