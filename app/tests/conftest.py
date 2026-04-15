import os
import asyncio
import pytest
import pytest_asyncio
import urllib.parse
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

# --- CRITICAL: SET ALL REQUIRED ENV VARS FIRST ---
os.environ["APP_ENV"] = "testing"
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "3306"
os.environ["DB_NAME"] = "testr"
os.environ["DB_USER"] = "root"
os.environ["DB_PASSWORD"] = "D@ksh1111"
os.environ["APP_SECRET_KEY"] = "test_secret_key_at_least_64_characters_long_to_satisfy_validation_rules"
os.environ["ADMIN_INITIAL_PASSWORD"] = "admin123"
os.environ["ADMIN_EMAIL"] = "admin@clg.ac.in"
os.environ["GCS_BUCKET_NAME"] = "test-bucket"

from core.config import settings
from main import app
from core.database import get_db

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a persistent engine for the session."""
    pw = urllib.parse.quote_plus(settings.DB_PASSWORD)
    db_url = f"mysql+aiomysql://{settings.DB_USER}:{pw}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    
    engine = create_async_engine(db_url, pool_pre_ping=True)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture that wraps each test in a transaction and rolls it back.
    """
    connection = await test_engine.connect()
    trans = await connection.begin()
    
    SessionMaker = sessionmaker(
        connection, class_=AsyncSession, expire_on_commit=False
    )
    session = SessionMaker()

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    yield session

    await session.close()
    try:
        if connection.in_transaction():
            await trans.rollback()
    except Exception:
        pass
    finally:
        await connection.close()
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Async client for testing FastAPI endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://testserver",
        headers={"X-Requested-With": "XMLHttpRequest"}
    ) as ac:
        yield ac

@pytest.fixture(autouse=True)
def mock_gcs(mocker):
    """Deep-mock GCS."""
    mock_storage = mocker.patch("google.cloud.storage.Client")
    mock_client = MagicMock()
    mock_storage.return_value = mock_client
    mock_client.bucket.return_value = MagicMock()
    return mock_client
