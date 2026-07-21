from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models import User
from app.services.auth_service import AuthService
from app.services.google_oauth import build_google_authorize_url, google_oauth_configured


def test_google_oauth_configured() -> None:
    assert google_oauth_configured(Settings(google_client_id="", google_client_secret="")) is False
    assert (
        google_oauth_configured(
            Settings(google_client_id="id", google_client_secret="secret")
        )
        is True
    )


def test_build_google_authorize_url_contains_client() -> None:
    settings = Settings(
        google_client_id="client-id",
        google_client_secret="secret",
        google_redirect_uri="http://localhost:8000/api/v1/auth/google/callback",
    )
    url = build_google_authorize_url(settings, state="abc")
    assert "client-id" in url
    assert "state=abc" in url
    assert "accounts.google.com" in url


@pytest.mark.asyncio
async def test_upsert_google_user_creates() -> None:
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    ]
    service = AuthService(db)
    user = await service.upsert_google_user(email="a@example.com", google_sub="sub-1")
    assert user.email == "a@example.com"
    assert user.google_sub == "sub-1"
    assert user.hashed_password is None
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_google_user_links_existing_email() -> None:
    existing = User(
        id=uuid4(),
        email="a@example.com",
        hashed_password="hash",
        google_sub=None,
    )
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=existing)),
    ]
    service = AuthService(db)
    user = await service.upsert_google_user(email="a@example.com", google_sub="sub-2")
    assert user is existing
    assert user.google_sub == "sub-2"
