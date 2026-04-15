import pytest
from httpx import AsyncClient
from starlette import status

@pytest.mark.asyncio
async def test_csrf_protection(client: AsyncClient):
    """Verifies that state-changing requests fail without X-Requested-With header."""
    from main import app
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as insecure_client:
        # Using a valid-looking but incorrect login to trigger CSRF check instead of Pydantic error
        response = await insecure_client.post("/api/auth/login", json={
            "email": "test@clg.ac.in",
            "password": "wrongpassword"
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "CSRF protection" in response.json()["detail"]

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Verifies the enhanced health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"

@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient):
    """Verifies login failure (401) for incorrect credentials."""
    response = await client.post("/api/auth/login", json={
        "email": "invalid@clg.ac.in",
        "password": "wrongpassword123"
    })
    # This should hit the service and return 401 because user doesn't exist
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
