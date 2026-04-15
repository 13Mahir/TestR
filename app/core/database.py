"""
Database connection and session management for the TestR.
"""
from typing import AsyncGenerator
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from core.config import settings

# engine kwargs mapping
engine_kwargs = {
    "echo": settings.APP_ENV == "development"
}

if not settings.db_url.startswith("sqlite"):
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 3600,
    })

engine = create_async_engine(settings.db_url, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    """SQLAlchemy 2.0 style Declarative Base."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for obtaining an asynchronous database session.
    Provides automatic resource management and rollback on failure.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Called on startup to verify the connection.
    Runs SELECT 1 via a raw connection to verify DB reachability.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("Database connection verified successfully.")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to the database at {settings.db_url}: {e}")
