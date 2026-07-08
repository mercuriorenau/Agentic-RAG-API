from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def app_with_mock_db():
    async def override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_validation_error_returns_422(app_with_mock_db) -> None:
    transport = ASGITransport(app=app_with_mock_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "short"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
@patch("app.services.auth_service.AuthService.register", new_callable=AsyncMock)
async def test_register_endpoint(mock_register, app_with_mock_db) -> None:
    user = MagicMock()
    user.id = "11111111-1111-1111-1111-111111111111"
    user.email = "user@example.com"
    mock_register.return_value = user

    transport = ASGITransport(app=app_with_mock_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"
