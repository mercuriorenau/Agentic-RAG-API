"""Auth helpers shared by integration tests."""

from httpx import AsyncClient

from tests.email_outbox import verification_outbox


async def register_verify_and_login(
    client: AsyncClient,
    email: str,
    password: str = "password123",
) -> str:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 201, register_response.text
    assert register_response.json()["email_verified"] is False
    assert verification_outbox.get("code")

    verify_response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "code": verification_outbox["code"]},
    )
    assert verify_response.status_code == 200, verify_response.text
    token = verify_response.json().get("access_token")
    assert token
    return token
