"""
Database connection and session management for the TestR.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from core.config import settings

# engine kwargs mapping
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 3600,
    "echo": settings.APP_ENV == "development"
}

engine = create_async_engine(settings.db_url, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session, commits on success,
    rolls back on exception, and always closes the session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except:
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
