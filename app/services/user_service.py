"""
services/user_service.py
Business logic for user management and authentication operations.
Auth-related functions are implemented here in Prompt 05.
User CRUD functions (create, bulk create, deactivate) are added in
Prompts 10-12.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, delete, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_password,
)
from models import (User, ActiveSession, IPLog, UserRole,
                    StudentProfile, Branch, School)
from utils.email_validator import (
    parse_email, build_student_email, build_teacher_email,
    EmailParseResult
)
import csv
import io


# ── IP logging ────────────────────────────────────────────────────────────────

async def log_ip_event(
    db: AsyncSession,
    action: str,
    ip_address: str,
    email_attempted: str,
    user_id: Optional[int] = None,
) -> None:
    """
    Appends a row to ip_logs. Never raises — errors are swallowed so
    that a logging failure never blocks a login or exam attempt.

    Args:
        action:          One of the IPLog action enum values as a string.
                         e.g. 'login_success', 'login_failed', 'logout',
                         'exam_attempt_start'
        ip_address:      IPv4 or IPv6 string from the request.
        email_attempted: The email string the caller provided.
        user_id:         The resolved user PK. None for failed logins.
    """
    try:
        entry = IPLog(
            user_id=user_id,
            email_attempted=email_attempted,
            ip_address=ip_address,
            action=action,
        )
        db.add(entry)
        await db.flush()   # write within current transaction, no commit yet
    except Exception:
        pass               # logging must never crash the caller


# ── Session management ────────────────────────────────────────────────────────

async def create_user_session(
    db: AsyncSession,
    user: User,
    ip_address: str,
) -> tuple[str, str]:
    """
    Creates a new auth session for the given user.

    Steps:
      1. Delete any existing active_sessions row for this user.
         (Enforces concurrent login prevention at DB level — the old
         jti becomes orphaned and get_current_user will reject it.)
      2. Generate new access + refresh token pair.
      3. Insert new active_sessions row.
      4. Flush (caller commits via get_db transaction).

    Returns:
        (access_token, refresh_token) as raw JWT strings.
    """
    # Step 1 — kill any existing session for this user
    await db.execute(
        delete(ActiveSession).where(ActiveSession.user_id == user.id)
    )

    # Step 2 — generate tokens
    token_data     = {"sub": user.email, "role": user.role.value}
    access_token,  a_jti = create_access_token(token_data)
    refresh_token, r_jti = create_refresh_token({"sub": user.email})

    # Step 3 — persist session record
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=7   # mirrors REFRESH_TOKEN_EXPIRE_DAYS
                 # we import settings here to avoid circular imports
    )
    # Import inside function to avoid top-level circular import
    from core.config import settings
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    session = ActiveSession(
        user_id=user.id,
        access_token_jti=a_jti,
        refresh_token_jti=r_jti,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    return access_token, refresh_token


async def rotate_session_tokens(
    db: AsyncSession,
    user: User,
    old_session: ActiveSession,
    ip_address: str,
) -> tuple[str, str]:
    """
    Issues a fresh access + refresh token pair and updates the
    existing active_sessions row in place (token rotation).

    Called by POST /api/auth/refresh.
    Does NOT delete and re-insert — updates the existing row so
    the session ID stays stable for any future audit.

    Returns:
        (new_access_token, new_refresh_token)
    """
    from core.config import settings

    token_data        = {"sub": user.email, "role": user.role.value}
    new_access,  a_jti = create_access_token(token_data)
    new_refresh, r_jti = create_refresh_token({"sub": user.email})

    new_expires = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    old_session.access_token_jti  = a_jti
    old_session.refresh_token_jti = r_jti
    old_session.ip_address        = ip_address
    old_session.expires_at        = new_expires

    db.add(old_session)
    await db.flush()

    return new_access, new_refresh


async def delete_user_session(
    db: AsyncSession,
    user_id: int,
) -> None:
    """
    Deletes the active session for the given user_id.
    Called on logout. Safe to call even if no session exists.
    """
    await db.execute(
        delete(ActiveSession).where(ActiveSession.user_id == user_id)
    )
    await db.flush()


# ── Password management ───────────────────────────────────────────────────────

async def change_user_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> tuple[bool, str]:
    """
    Changes a user's password after verifying the current one.

    Returns:
        (True, "Password changed successfully.") on success.
        (False, "<reason>") on failure — caller raises HTTP error.

    Side effects on success:
        - Updates user.password_hash
        - Sets user.force_password_reset = False
        - Flushes (caller commits)
    """
    if not verify_password(current_password, user.password_hash):
        return False, "Current password is incorrect."

    if current_password == new_password:
        return False, "New password must differ from the current password."

    user.password_hash        = hash_password(new_password)
    user.force_password_reset = False
    db.add(user)
    await db.flush()

    return True, "Password changed successfully."

# ── Single user creation ──────────────────────────────────────────────────────

async def create_single_user(
    db: AsyncSession,
    email: str,
    password: str,
    created_by_id: int,
) -> tuple[Optional[User], Optional[str]]:
    """
    Creates a single user (admin, teacher, or student) from an email
    and password. Role and name are derived from the email pattern.

    For students: also creates the student_profiles row and validates
    that the branch_code in the email exists in the branches table.

    Returns:
        (User, None)         on success
        (None, error_string) on failure

    Does NOT commit — caller commits.
    Does NOT write logs — caller writes logs after this returns.
    """
    # Parse email to determine role and extract components
    parsed = parse_email(email)
    if not parsed.is_valid:
        return None, f"Invalid email format: {parsed.error}"

    # Check for duplicate email
    existing = await db.execute(
        select(User).where(User.email == email)
    )
    if existing.scalar_one_or_none() is not None:
        return None, f"Email already exists: {email}"

    # Build user object
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole(parsed.role),
        first_name=parsed.first_name or "",
        last_name=parsed.last_name or "",
        is_active=True,
        force_password_reset=True,
        # All newly created users must change password on first login
    )
    db.add(user)
    await db.flush()  # Get user.id before creating profile

    # For students: create student_profiles row
    if parsed.role == "student":
        # Validate branch exists
        branch_result = await db.execute(
            select(Branch).where(Branch.code == parsed.branch_code)
        )
        branch = branch_result.scalar_one_or_none()
        if branch is None:
            return None, (
                f"Branch code '{parsed.branch_code}' does not exist. "
                f"Add it via the branches table first."
            )

        # Validate school code matches branch's school
        school_result = await db.execute(
            select(School).where(School.id == branch.school_id)
        )
        school = school_result.scalar_one_or_none()
        if school is None or school.code != parsed.school_code:
            return None, (
                f"School code '{parsed.school_code}' does not match "
                f"the school for branch '{parsed.branch_code}'."
            )

        profile = StudentProfile(
            user_id=user.id,
            batch_year=parsed.batch_year,
            branch_id=branch.id,
            roll_number=parsed.roll_number,
        )
        db.add(profile)
        await db.flush()

    # Refresh user to load server-set defaults (created_at, etc.)
    # after flush — avoids MissingGreenlet from expired-attribute lazy load
    await db.refresh(user)
    return user, None


# ── Bulk student creation ─────────────────────────────────────────────────────

async def bulk_create_students(
    db: AsyncSession,
    batch_year: str,
    branch_code: str,
    roll_start: int,
    roll_end: int,
    default_password: str,
    created_by_id: int,
) -> tuple[int, int, int, list[str]]:
    """
    Creates student accounts for all roll numbers in the given range
    for a specific batch year and branch.

    Email format: {batch_year}{branch_code}{roll:03d}@{school}.clg.ac.in
    e.g. 22CSE001@se.clg.ac.in through 22CSE060@se.clg.ac.in

    Returns:
        (created_count, skipped_count, failed_count, error_list)

    Skipped = email already exists (not an error, idempotent).
    Failed  = any other error (branch not found, DB error, etc.).
    Does NOT commit — caller commits once after all inserts.
    """
    # Validate branch exists and get school code
    branch_result = await db.execute(
        select(Branch).where(Branch.code == branch_code)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        return 0, 0, 1, [
            f"Branch code '{branch_code}' does not exist in the database."
        ], []

    school_result = await db.execute(
        select(School).where(School.id == branch.school_id)
    )
    school = school_result.scalar_one_or_none()
    if school is None:
        return 0, 0, 1, [
            f"School for branch '{branch_code}' not found."
        ], []

    password_hash = hash_password(default_password)
    created = 0
    skipped = 0
    failed  = 0
    errors  = []

    created_ids = []
    for roll in range(roll_start, roll_end + 1):
        roll_str = f"{roll:03d}"
        try:
            email = build_student_email(
                batch_year=batch_year,
                branch_code=branch_code,
                roll_number=roll_str,
                school_code=school.code,
            )
        except ValueError as e:
            failed += 1
            errors.append(f"Roll {roll_str}: {str(e)}")
            continue

        # Check for duplicate
        existing = await db.execute(
            select(User.id).where(User.email == email)
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        try:
            # Create user
            user = User(
                email=email,
                password_hash=password_hash,
                role=UserRole.student,
                first_name=batch_year + branch_code,
                last_name=roll_str,
                is_active=True,
                force_password_reset=True,
            )
            db.add(user)
            await db.flush()

            # Create profile
            profile = StudentProfile(
                user_id=user.id,
                batch_year=batch_year,
                branch_id=branch.id,
                roll_number=roll_str,
            )
            db.add(profile)
            await db.flush()

            created += 1
            created_ids.append(user.id)

        except Exception as e:
            failed += 1
            errors.append(f"Roll {roll_str} ({email}): {str(e)}")

    return created, skipped, failed, errors, created_ids


# ── Bulk teacher creation from CSV ────────────────────────────────────────────

async def bulk_create_teachers_from_csv(
    db: AsyncSession,
    csv_bytes: bytes,
    default_password: str,
    created_by_id: int,
) -> tuple[int, int, int, list[str]]:
    """
    Creates teacher accounts from a CSV file.

    Expected CSV format (with header row):
        first_name,last_name
        John,Smith
        Jane,Doe

    Generates email as: first.last@clg.ac.in
    If a name collision occurs (two teachers with same first+last),
    the second one is skipped and reported in errors.

    Returns:
        (created_count, skipped_count, failed_count, error_list)

    Does NOT commit — caller commits.
    """
    created  = 0
    skipped  = 0
    failed   = 0
    errors   = []
    created_ids = []

    # Parse CSV from bytes
    try:
        text    = csv_bytes.decode("utf-8-sig")  # handle BOM if present
        reader  = csv.DictReader(io.StringIO(text))

        # Validate expected columns exist
        if reader.fieldnames is None:
            return 0, 0, 1, ["CSV file is empty or has no header row."]

        # Normalise column names to lowercase stripped
        fieldnames_lower = [f.strip().lower() for f in reader.fieldnames]
        if "first_name" not in fieldnames_lower or \
           "last_name"  not in fieldnames_lower:
            return 0, 0, 1, [
                "CSV must have columns: first_name, last_name. "
                f"Found: {', '.join(reader.fieldnames)}"
            ]

        rows = list(reader)

    except UnicodeDecodeError:
        return 0, 0, 1, ["CSV file must be UTF-8 encoded."]
    except Exception as e:
        return 0, 0, 1, [f"Failed to parse CSV: {str(e)}"]

    if not rows:
        return 0, 0, 0, ["CSV file has no data rows."]

    if len(rows) > 500:
        return 0, 0, 1, [
            "CSV file exceeds maximum of 500 teacher rows per upload."
        ]

    password_hash = hash_password(default_password)

    for i, row in enumerate(rows, start=2):  # start=2: row 1 is header
        # Extract and strip values (handle both cases of column names)
        first = (row.get("first_name") or row.get("First_name") or "").strip()
        last  = (row.get("last_name")  or row.get("Last_name")  or "").strip()

        if not first or not last:
            failed += 1
            errors.append(
                f"Row {i}: first_name and last_name must not be empty."
            )
            continue

        try:
            email = build_teacher_email(first, last)
        except ValueError as e:
            failed += 1
            errors.append(f"Row {i} ({first} {last}): {str(e)}")
            continue

        # Check for duplicate
        existing = await db.execute(
            select(User.id).where(User.email == email)
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        try:
            user = User(
                email=email,
                password_hash=password_hash,
                role=UserRole.teacher,
                first_name=first.capitalize(),
                last_name=last.capitalize(),
                is_active=True,
                force_password_reset=True,
            )
            db.add(user)
            await db.flush()
            created += 1
            created_ids.append(user.id)

        except Exception as e:
            failed += 1
            errors.append(f"Row {i} ({email}): {str(e)}")

    return created, skipped, failed, errors, created_ids


# ── Bulk deactivation ─────────────────────────────────────────────────────────

async def bulk_deactivate_students(
    db: AsyncSession,
    batch_year: str,
    branch_code: Optional[str],
) -> int:
    """
    Deactivates all student accounts for a batch year.
    If branch_code is provided, only that branch is deactivated.
    If branch_code is None, entire batch is deactivated.

    Also deletes active_sessions for all deactivated users so they
    are immediately logged out.

    Returns count of deactivated users.
    Does NOT commit — caller commits.
    """
    # Find matching student profiles
    query = (
        select(StudentProfile)
        .join(Branch, StudentProfile.branch_id == Branch.id)
        .where(StudentProfile.batch_year == batch_year)
    )
    if branch_code:
        query = query.where(Branch.code == branch_code.upper())

    result = await db.execute(query)
    profiles = result.scalars().all()

    if not profiles:
        return 0

    user_ids = [p.user_id for p in profiles]

    # Deactivate users
    await db.execute(
        update(User)
        .where(User.id.in_(user_ids))
        .values(is_active=False)
    )

    # Immediately invalidate their sessions
    await db.execute(
        delete(ActiveSession)
        .where(ActiveSession.user_id.in_(user_ids))
    )

    await db.flush()
    return len(user_ids)


# ── Bulk activation ──────────────────────────────────────────────────────────

async def bulk_activate_students(
    db: AsyncSession,
    batch_year: str,
    branch_code: Optional[str],
) -> int:
    """
    Activates (re-enables) all student accounts for a batch year.
    If branch_code is provided, only that branch is activated.
    If branch_code is None, entire batch is activated.

    Returns count of activated users.
    Does NOT commit — caller commits.
    """
    # Find matching student profiles whose user is currently inactive
    query = (
        select(StudentProfile)
        .join(Branch, StudentProfile.branch_id == Branch.id)
        .join(User, User.id == StudentProfile.user_id)
        .where(StudentProfile.batch_year == batch_year)
        .where(User.is_active == False)
    )
    if branch_code:
        query = query.where(Branch.code == branch_code.upper())

    result = await db.execute(query)
    profiles = result.scalars().all()

    if not profiles:
        return 0

    user_ids = [p.user_id for p in profiles]

    # Activate users
    await db.execute(
        update(User)
        .where(User.id.in_(user_ids))
        .values(is_active=True)
    )

    await db.flush()
    return len(user_ids)


# ── List users ────────────────────────────────────────────────────────────────

async def list_users(
    db: AsyncSession,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[User], int]:
    """
    Returns paginated list of users with optional filters.

    Filters:
        role:      Filter by role string ('admin','teacher','student')
        is_active: Filter by active status
        search:    Case-insensitive search against email, first_name,
                   last_name (uses SQL LIKE)

    Returns:
        (users_list, total_count)
    """
    base_query = select(User)
    count_query = select(func.count(User.id))

    if role:
        base_query  = base_query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    if is_active is not None:
        base_query  = base_query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    if search:
        pattern = f"%{search}%"
        from sqlalchemy import or_
        condition = or_(
            User.email.ilike(pattern),
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
        )
        base_query  = base_query.where(condition)
        count_query = count_query.where(condition)

    # Total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginated results — newest first
    users_result = await db.execute(
        base_query
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = list(users_result.scalars().all())

    return users, total


# ── Toggle user active status ─────────────────────────────────────────────────

async def toggle_user_active(
    db: AsyncSession,
    target_user_id: int,
) -> tuple:
    """
    Toggles a user's is_active flag (activate ↔ deactivate).

    If deactivating, also deletes their active session so they
    are immediately logged out.

    Returns:
        (new_is_active_bool, error_string_or_None)

    Does NOT commit — caller commits.
    """
    result = await db.execute(
        select(User).where(User.id == target_user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        return None, "User not found."

    new_status = not user.is_active
    user.is_active = new_status

    # If deactivating, immediately kill their session
    if not new_status:
        await db.execute(
            delete(ActiveSession)
            .where(ActiveSession.user_id == target_user_id)
        )

    await db.flush()
    return new_status, None


import secrets
from datetime import datetime, timedelta, timezone
# (models.PasswordResetToken is imported inline below)

async def generate_password_reset_token(
    db: AsyncSession,
    target_user_id: int,
    admin_id: int,
) -> tuple[Optional['PasswordResetToken'], Optional[str]]:
    """
    Generates a cryptographically secure password reset token for
    a target user. Called by admin only — no email is sent.
    The token is displayed in the admin panel for the admin to
    share manually.

    Steps:
      1. Verify target user exists and is not the admin themselves.
         (Admin resets their own password via change-password page.)
      2. Delete any existing unused tokens for this user to avoid
         token accumulation.
      3. Generate a 64-character hex token using secrets.token_hex(32).
      4. Set expiry to 48 hours from now (UTC).
      5. Insert new PasswordResetToken row.

    Returns:
        (PasswordResetToken, None)   on success
        (None, error_string)         on failure

    Does NOT commit — caller commits.
    """
    from models import PasswordResetToken

    # Verify target user exists
    user_result = await db.execute(
        select(User).where(User.id == target_user_id)
    )
    target_user = user_result.scalar_one_or_none()
    if target_user is None:
        return None, f"User with id {target_user_id} not found."

    # Admin cannot reset their own password via this endpoint
    if target_user_id == admin_id:
        return None, (
            "Admins cannot use this endpoint to reset their own password. "
            "Use the change-password page instead."
        )

    # Delete existing unused tokens for this user
    await db.execute(
        delete(PasswordResetToken).where(
            and_(
                PasswordResetToken.user_id == target_user_id,
                PasswordResetToken.is_used == False,
            )
        )
    )
    await db.flush()

    # Generate token
    raw_token  = secrets.token_hex(32)   # 64 hex chars
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

    token_row = PasswordResetToken(
        user_id=target_user_id,
        token=raw_token,
        created_by=admin_id,
        is_used=False,
        expires_at=expires_at,
    )
    db.add(token_row)
    await db.flush()

    return token_row, None


async def consume_password_reset_token(
    db: AsyncSession,
    raw_token: str,
    new_password: str,
) -> tuple[bool, str]:
    """
    Validates and consumes a password reset token, applying the
    new password to the associated user.

    Steps:
      1. Find the token row by raw_token value.
      2. Check is_used == False.
      3. Check expires_at > now(UTC).
      4. Hash and apply new_password to user.
      5. Set user.force_password_reset = False.
      6. Mark token as used (is_used = True).
      7. Delete the user's active session so they must log in fresh.

    Returns:
        (True,  "Password reset successfully.")  on success
        (False, error_string)                    on failure

    Does NOT commit — caller commits.
    """
    from models import PasswordResetToken, ActiveSession

    if len(new_password) < 8:
        return False, "New password must be at least 8 characters."

    # Find token
    token_result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == raw_token
        )
    )
    token_row = token_result.scalar_one_or_none()

    if token_row is None:
        return False, "Invalid or expired reset token."

    if token_row.is_used:
        return False, "This reset token has already been used."

    # Check expiry — make timezone-aware for comparison
    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        return False, "This reset token has expired. Request a new one."

    # Load user
    user_result = await db.execute(
        select(User).where(User.id == token_row.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        return False, "User associated with this token no longer exists."

    # Apply new password
    user.password_hash        = hash_password(new_password)
    user.force_password_reset = False
    db.add(user)

    # Mark token as used
    token_row.is_used = True
    db.add(token_row)

    # Invalidate active session — user must log in with new password
    await db.execute(
        delete(ActiveSession).where(ActiveSession.user_id == user.id)
    )

    await db.flush()
    return True, "Password reset successfully."


async def get_active_reset_token(
    db: AsyncSession,
    target_user_id: int,
) -> Optional['PasswordResetToken']:
    """
    Returns the most recent unused, unexpired password reset token
    for a user, or None if none exists.
    Used by admin panel to show whether a token is pending.
    """
    from models import PasswordResetToken

    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(PasswordResetToken)
        .where(
            and_(
                PasswordResetToken.user_id == target_user_id,
                PasswordResetToken.is_used == False,
                PasswordResetToken.expires_at > now,
            )
        )
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
