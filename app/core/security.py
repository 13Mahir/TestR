"""
core/security.py
Security utilities: password hashing, JWT token creation/decoding,
HttpOnly cookie management, and token extraction from requests.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Response, Request

from core.config import settings

# ── Constants ────────────────────────────────────────────────────────────────
ACCESS_COOKIE  = "access_token"
REFRESH_COOKIE = "refresh_token"
ALGORITHM      = "HS256"

# ── Password hashing ─────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    """Hashes a plain-text password using bcrypt. Returns the hash string."""
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    """
    Verifies a plain-text password against a bcrypt hash.
    Returns True if they match, False otherwise.
    """
    return pwd_context.verify(plain, hashed)

# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(data: dict) -> tuple[str, str]:
    """
    Creates a signed JWT access token.

    `data` must contain:
        'sub'  - user email string
        'role' - user role string

    Returns:
        (token_string, jti) where jti is the unique token ID stored
        in active_sessions for session tracking and concurrent login
        prevention.

    Token lifetime: settings.ACCESS_TOKEN_EXPIRE_MINUTES from now (UTC).
    """
    jti     = str(uuid.uuid4())
    now     = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub":  data["sub"],
        "role": data["role"],
        "jti":  jti,
        "type": "access",
        "iat":  now,
        "exp":  expires,
    }

    token = jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=ALGORITHM)
    return token, jti


def create_refresh_token(data: dict) -> tuple[str, str]:
    """
    Creates a signed JWT refresh token.

    `data` must contain:
        'sub' - user email string

    Returns:
        (token_string, jti) where jti is the unique token ID stored
        in active_sessions.

    Token lifetime: settings.REFRESH_TOKEN_EXPIRE_DAYS days from now (UTC).
    """
    jti     = str(uuid.uuid4())
    now     = datetime.now(timezone.utc)
    expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub":  data["sub"],
        "jti":  jti,
        "type": "refresh",
        "iat":  now,
        "exp":  expires,
    }

    token = jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=ALGORITHM)
    return token, jti


# ── Token decoding ────────────────────────────────────────────────────────────

def decode_token(token: str) -> Optional[dict]:
    """
    Decodes and validates a JWT token signature and expiry.

    Returns the full payload dict if valid.
    Returns None if the token is expired, malformed, or has an
    invalid signature.

    Does NOT check jti against the database — that is done in
    core/dependencies.py get_current_user().
    """
    try:
        payload = jwt.decode(
            token,
            settings.APP_SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return payload
    except JWTError:
        return None


# ── Cookie helpers ────────────────────────────────────────────────────────────

def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """
    Sets both the access token and refresh token as HttpOnly cookies
    on the given Response object.

    Cookie attributes:
        httponly  = True          (JS cannot read the cookie)
        secure    = True only in production (False allows HTTP on localhost)
        samesite  = "lax"        (sent on top-level navigation, blocks CSRF)
        path      = "/"          (available to all routes)
    """
    secure = settings.is_production

    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Clears both auth cookies by setting them to an empty string
    with max_age=0. This is the correct logout cookie deletion method.

    Do NOT use response.delete_cookie() — it omits secure/samesite
    attributes, which causes browsers to ignore the deletion if those
    attributes were set on creation.
    """
    secure = settings.is_production

    response.set_cookie(
        key=ACCESS_COOKIE,
        value="",
        max_age=0,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value="",
        max_age=0,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


# ── Token extraction from request ────────────────────────────────────────────

def get_token_from_request(
    request: Request,
    token_type: str = "access",
) -> Optional[str]:
    """
    Extracts a token string from the incoming request's cookies.

    Args:
        token_type: "access" reads ACCESS_COOKIE,
                    "refresh" reads REFRESH_COOKIE.

    Returns the raw token string, or None if the cookie is absent
    or empty.
    """
    cookie_name = ACCESS_COOKIE if token_type == "access" else REFRESH_COOKIE
    value = request.cookies.get(cookie_name)
    return value if value else None
