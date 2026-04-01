"""
Main entry point for the TestR.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from core.config import settings
from core.database import init_db
import models

from routers import auth, admin, teacher, student, forum, notifications, discussion


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initializes database to check DB is reachable
    await init_db()
    print(f"Database connection verified successfully. APP_ENV: {settings.APP_ENV}")
    yield


app = FastAPI(title="TestR API", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS middleware
if settings.APP_ENV == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Exception handlers
@app.exception_handler(401)
async def unauthorized_exception_handler(request: Request, exc: Exception):
    detail = getattr(exc, "detail", "Unauthorized")
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": detail})
    return JSONResponse(status_code=401, content={"detail": detail})


@app.exception_handler(403)
async def forbidden_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=403, content={"detail": "Forbidden"})

import traceback
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc), "traceback": tb})


# Routes
@app.get("/")
async def root():
    return RedirectResponse(url="/static/pages/index.html")


@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.APP_ENV}


# Include routers
app.include_router(auth.router, prefix="/api/auth")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(teacher.router, prefix="/api/teacher")
app.include_router(student.router, prefix="/api/student")
app.include_router(forum.router, prefix="/api/forum")
app.include_router(discussion.router) # Prefix is handled in router
app.include_router(notifications.router, prefix="/api/notifications")

