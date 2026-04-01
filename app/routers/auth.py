"""
routers/auth.py
Authentication endpoints: login, logout, token refresh, /me,
change-password.
All routes are prefixed with /api/auth in main.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user, require_password_not_reset_pending
from core.security import (
    verify_password,
    set_auth_cookies,
    clear_auth_cookies,
    get_token_from_request,
    decode_token,
)
from models import User, ActiveSession
from schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    ChangePasswordRequest,
    RefreshResponse,
    MessageResponse,
)
from services.user_service import (
    log_ip_event,
    create_user_session,
    rotate_session_tokens,
    delete_user_session,
    change_user_password,
)

router = APIRouter(tags=["auth"])


def _get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP from the request.
    Checks X-Forwarded-For first (set by Cloud Run / load balancers),
    falls back to request.client.host.
    Always returns a string — never None.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may contain a comma-separated list;
        # the leftmost is the original client.
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ── POST /api/auth/login ──────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate and receive HttpOnly session cookies.",
)
async def login(
    body:     LoginRequest,
    request:  Request,
    response: Response,
    db:       AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Authenticates a user by email + password.

    On success:
      - Sets access_token and refresh_token as HttpOnly cookies.
      - Creates/replaces the active_sessions row (concurrent login
        prevention).
      - Logs the event to ip_logs with action='login_success'.

    On failure:
      - Logs to ip_logs with action='login_failed'.
      - Returns HTTP 401 — same message for wrong email OR wrong
        password (prevents user enumeration).
    """
    ip = _get_client_ip(request)

    # Look up user by email
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user: User | None = result.scalar_one_or_none()

    # Wrong email or wrong password — identical response to prevent
    # user enumeration attacks
    if user is None or not verify_password(body.password, user.password_hash):
        await log_ip_event(
            db=db,
            action="login_failed",
            ip_address=ip,
            email_attempted=body.email,
            user_id=None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Account deactivated
    if not user.is_active:
        await log_ip_event(
            db=db,
            action="login_failed",
            ip_address=ip,
            email_attempted=body.email,
            user_id=user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated. Contact an administrator.",
        )

    # Create session (deletes existing session → concurrent login prevention)
    access_token, refresh_token = await create_user_session(
        db=db,
        user=user,
        ip_address=ip,
    )

    # Log success
    await log_ip_event(
        db=db,
        action="login_success",
        ip_address=ip,
        email_attempted=body.email,
        user_id=user.id,
    )

    # Set cookies on the response object
    set_auth_cookies(response, access_token, refresh_token)

    return LoginResponse(
        message="Login successful.",
        role=user.role.value,
        email=user.email,
        full_name=user.full_name,
        force_password_reset=user.force_password_reset,
    )


# ── POST /api/auth/logout ─────────────────────────────────────────────────────

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Invalidate the current session and clear cookies.",
)
async def logout(
    request:  Request,
    response: Response,
    db:       AsyncSession = Depends(get_db),
    # get_current_user only — do NOT use require_password_not_reset_pending
    # so that users with a forced reset can still log out
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Logs the user out:
      - Deletes active_sessions row.
      - Clears HttpOnly cookies.
      - Logs to ip_logs with action='logout'.
    """
    ip = _get_client_ip(request)

    await delete_user_session(db=db, user_id=current_user.id)

    await log_ip_event(
        db=db,
        action="logout",
        ip_address=ip,
        email_attempted=current_user.email,
        user_id=current_user.id,
    )

    clear_auth_cookies(response)

    return MessageResponse(message="Logged out successfully.")


# ── POST /api/auth/refresh ────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Use the refresh token cookie to obtain a new access token.",
)
async def refresh_tokens(
    request:  Request,
    response: Response,
    db:       AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """
    Token refresh flow:
      1. Read refresh token from cookie.
      2. Decode and validate it.
      3. Confirm type == 'refresh'.
      4. Look up jti in active_sessions.
      5. Load user, confirm active.
      6. Rotate both tokens (update session row in place).
      7. Set new cookies.

    Returns HTTP 401 on any validation failure — the frontend should
    redirect to /pages/login.html on receiving 401 from this endpoint.
    """
    ip = _get_client_ip(request)

    raw_token = get_token_from_request(request, token_type="refresh")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing.",
        )

    payload = decode_token(raw_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalid or expired.",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token.",
        )

    # Find session by refresh jti
    result = await db.execute(
        select(ActiveSession).where(
            ActiveSession.refresh_token_jti == jti
        )
    )
    session: ActiveSession | None = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found. Please log in again.",
        )

    # Load user
    user_result = await db.execute(
        select(User).where(User.id == session.user_id)
    )
    user: User | None = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated.",
        )

    # Rotate tokens
    new_access, new_refresh = await rotate_session_tokens(
        db=db,
        user=user,
        old_session=session,
        ip_address=ip,
    )

    set_auth_cookies(response, new_access, new_refresh)

    return RefreshResponse(message="Tokens refreshed successfully.")


# ── GET /api/auth/me ──────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=MeResponse,
    summary="Return the currently authenticated user's profile.",
)
async def get_me(
    # get_current_user only — do NOT add password-reset guard here
    # so the frontend can read role/force_password_reset on every page load
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    """
    Returns the authenticated user's basic profile.
    Used by every page on load to verify auth state and get role info.

    The frontend auth.js calls this endpoint on every page load:
      - 401 response → redirect to /pages/login.html
      - 200 with force_password_reset=true → redirect to change-password page
      - 200 → render the page normally
    """
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        force_password_reset=current_user.force_password_reset,
    )


# ── POST /api/auth/change-password ───────────────────────────────────────────

@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change the authenticated user's password.",
)
async def change_password(
    body:    ChangePasswordRequest,
    request: Request,
    response: Response,
    db:      AsyncSession = Depends(get_db),
    # get_current_user only — this route must work even when
    # force_password_reset is True (it is the resolution for that state)
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Changes the user's password.

    - Verifies current password before accepting new one.
    - Clears force_password_reset flag on success.
    - Rotates the session tokens after a successful change so the
      new password takes effect immediately without requiring re-login.
    - Returns HTTP 400 if current password is wrong or new == current.
    """
    ip = _get_client_ip(request)

    success, message = await change_user_password(
        db=db,
        user=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    # Rotate session tokens so the old access token (which may be
    # cached in the browser) is invalidated.
    result = await db.execute(
        select(ActiveSession).where(
            ActiveSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if session:
        new_access, new_refresh = await rotate_session_tokens(
            db=db,
            user=current_user,
            old_session=session,
            ip_address=ip,
        )
        set_auth_cookies(response, new_access, new_refresh)

    return MessageResponse(message=message)
