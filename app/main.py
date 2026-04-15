"""
Main entry point for the TestR.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from core.config import settings
from core.database import init_db
from core.exceptions import (
    AppException, NotFoundException, ForbiddenException,
    UnauthorizedException, ValidationException, ConflictException,
    SystemException
)
import models

from routers import auth, admin, teacher, student, forum, notifications, discussion
from core.database import get_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initializes database to check DB is reachable
    await init_db()
    print(f"Database connection verified successfully. APP_ENV: {settings.APP_ENV}")
    yield


from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI(title="TestR API", lifespan=lifespan)

# ── Security Middleware ────────────────────────────────────────────────────────

# 1. Trusted Host Middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=settings.ALLOWED_HOSTS
)

# 2. Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. CSRF Protection for state-changing methods
        if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            if not request.headers.get("X-Requested-With"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF protection: X-Requested-With header missing"}
                )

        response = await call_next(request)
        
        # 2. Prevent Clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # 3. Prevent MIME Sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # 4. Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # 5. XSS Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # 6. Content Security Policy (CSP)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 3. CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException):
    return JSONResponse(status_code=404, content={"detail": exc.message, "details": exc.details})

@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException):
    return JSONResponse(status_code=403, content={"detail": exc.message or "Forbidden"})

@app.exception_handler(UnauthorizedException)
async def unauthorized_handler(request: Request, exc: UnauthorizedException):
    return JSONResponse(status_code=401, content={"detail": exc.message or "Unauthorized"})

@app.exception_handler(ValidationException)
async def validation_handler(request: Request, exc: ValidationException):
    return JSONResponse(status_code=400, content={"detail": exc.message, "details": exc.details})

@app.exception_handler(ConflictException)
async def conflict_handler(request: Request, exc: ConflictException):
    return JSONResponse(status_code=409, content={"detail": exc.message, "details": exc.details})

@app.exception_handler(SystemException)
async def system_exception_handler(request: Request, exc: SystemException):
    return JSONResponse(status_code=500, content={"detail": exc.message})

import traceback
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Only show traceback in development
    content = {"detail": "An internal server error occurred."}
    if settings.APP_ENV == "development":
        content["detail"] = str(exc)
        content["traceback"] = traceback.format_exc()
    return JSONResponse(status_code=500, content=content)


# Routes
@app.get("/")
async def root():
    return RedirectResponse(url="/static/pages/index.html")


@app.get("/health")
async def health_check(db: "AsyncSession" = Depends(get_db)):
    """
    Enhanced health check that verifies database connectivity.
    """
    from sqlalchemy import text
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        import sys
        print(f"DEBUG: Health check DB error: {e}", file=sys.stderr)
        db_status = "disconnected"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "env": settings.APP_ENV
    }


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Include routers
app.include_router(auth.router, prefix="/api/auth")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(teacher.router, prefix="/api/teacher")
app.include_router(student.router, prefix="/api/student")
app.include_router(forum.router, prefix="/api/forum")
app.include_router(discussion.router) # Prefix is handled in router
app.include_router(notifications.router, prefix="/api/notifications")

