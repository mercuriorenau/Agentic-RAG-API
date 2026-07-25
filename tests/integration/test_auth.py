import pytest
from httpx import AsyncClient

from tests.auth_helpers import register_verify_and_login
from tests.email_outbox import verification_outbox


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    token = await register_verify_and_login(client, "user@example.com")
    assert token


@pytest.mark.asyncio
async def test_login_before_verify_returns_401(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "pending@example.com", "password": "password123"},
    )
    assert register_response.status_code == 201
    assert register_response.json()["email_verified"] is False

    # No users row until verified — login cannot succeed.
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "pending@example.com", "password": "password123"},
    )
    assert login_response.status_code == 401


@pytest.mark.asyncio
async def test_verify_email_via_link(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "link@example.com", "password": "password123"},
    )
    token = verification_outbox["token"]
    response = await client.get(f"/api/v1/auth/verify-email?token={token}", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    location = response.headers["location"]
    assert "email_verified=1" in location
    assert "auth_token=" in location
    assert "auth_email=" in location


@pytest.mark.asyncio
async def test_verify_email_code_returns_token(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "code@example.com", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "code@example.com", "code": verification_outbox["code"]},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_duplicate_register_returns_409(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "password123"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    # Pending (unverified) signup can be refreshed — not a conflict.
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    # After verify, further register attempts conflict.
    await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "dup@example.com", "code": verification_outbox["code"]},
    )
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_forgot_password_requires_code_before_change(client: AsyncClient) -> None:
    await register_verify_and_login(client, "reset@example.com", password="oldpass1")
    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@example.com"},
    )
    assert forgot.status_code == 200
    assert verification_outbox.get("kind") == "reset"
    reset_code = verification_outbox["code"]

    bad = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": "reset@example.com", "code": "000000", "new_password": "newpass1"},
    )
    assert bad.status_code == 400

    # Old password still works because code was never confirmed.
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "oldpass1"},
    )
    assert old_login.status_code == 200

    good = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": "reset@example.com", "code": reset_code, "new_password": "newpass1"},
    )
    assert good.status_code == 200
    assert "access_token" in good.json()

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "newpass1"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/documents")
    assert response.status_code == 401
