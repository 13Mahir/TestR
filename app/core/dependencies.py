"""
core/dependencies.py
FastAPI dependency functions for authentication, role enforcement,
and force-password-reset checking. Used via Depends() in all routes.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import decode_token, get_token_from_request
from models import User, ActiveSession, UserRole


# ── Core auth dependency ──────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates the incoming request's access token cookie and returns
    the authenticated User ORM object.

    Validation steps:
      1. Extract access token from cookies.
      2. Decode and verify JWT signature + expiry.
      3. Confirm token type == 'access'.
      4. Look up jti in active_sessions (concurrent session check).
      5. Confirm the session has not expired.
      6. Load the User record from the database.
      7. Confirm the user account is active.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )

    # Step 1 — extract raw token string from cookie
    token = get_token_from_request(request, token_type="access")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing",
        )

    # Step 2 — decode and verify signature / expiry
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
        )

    # Step 3 — confirm token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Step 4 — check jti exists in active_sessions
    jti = payload.get("jti")
    if not jti:
        raise credentials_exception

    result = await db.execute(
        select(ActiveSession).where(ActiveSession.access_token_jti == jti)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or replaced by a newer login",
        )

    # Step 5 — check session wall-clock expiry
    now = datetime.now(timezone.utc)
    # expires_at from DB is timezone-naive UTC — make it aware for comparison
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone as tz
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now > expires_at:
        await db.delete(session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    # Step 6 — load user
    email = payload.get("sub")
    if not email:
        raise credentials_exception

    user_result = await db.execute(
        select(User).where(User.email == email)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Step 7 — check account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    return user


# ── Role guards ───────────────────────────────────────────────────────────────

async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Raises HTTP 403 if the authenticated user is not an admin."""
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_teacher(
    current_user: User = Depends(get_current_user),
) -> User:
    """Raises HTTP 403 if the authenticated user is not a teacher."""
    if current_user.role != UserRole.teacher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher access required",
        )
    return current_user


async def require_student(
    current_user: User = Depends(get_current_user),
) -> User:
    """Raises HTTP 403 if the authenticated user is not a student."""
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required",
        )
    return current_user


async def require_admin_or_teacher(
    current_user: User = Depends(get_current_user),
) -> User:
    """Raises HTTP 403 if the user is neither admin nor teacher."""
    if current_user.role not in (UserRole.admin, UserRole.teacher):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or teacher access required",
        )
    return current_user


# ── Force-password-reset guard ────────────────────────────────────────────────

async def require_password_not_reset_pending(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Raises HTTP 403 with detail "PASSWORD_RESET_REQUIRED" if the user
    has a pending forced password reset set by an admin.

    Add this dependency to every protected route EXCEPT:
        POST /api/auth/change-password
        POST /api/auth/logout
        GET  /api/auth/me

    The frontend checks for this specific detail string and redirects
    to the password change page automatically.
    """
    if current_user.force_password_reset:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PASSWORD_RESET_REQUIRED",
        )
    return current_user


# ── Active user composite dependencies ───────────────────────────────────────
# These combine role check + password-reset check in one Depends().
# Use these on all real feature routes (not on /me, /logout, /change-password).

async def get_active_admin(
    user: User = Depends(require_admin),
    _: User    = Depends(require_password_not_reset_pending),
) -> User:
    """Admin user with no pending password reset."""
    return user


async def get_active_teacher(
    user: User = Depends(require_teacher),
    _: User    = Depends(require_password_not_reset_pending),
) -> User:
    """Teacher user with no pending password reset."""
    return user


async def get_active_student(
    user: User = Depends(require_student),
    _: User    = Depends(require_password_not_reset_pending),
) -> User:
    """Student user with no pending password reset."""
    return user
