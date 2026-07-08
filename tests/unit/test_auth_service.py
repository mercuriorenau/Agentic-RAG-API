import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models import User
from app.schemas.auth import UserRegister
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_register_creates_user() -> None:
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    service = AuthService(db)
    user = await service.register(UserRegister(email="new@example.com", password="password123"))

    assert user.email == "new@example.com"
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_duplicate_email_raises_409() -> None:
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=User()))

    service = AuthService(db)
    with pytest.raises(HTTPException) as exc:
        await service.register(UserRegister(email="dup@example.com", password="password123"))
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_authenticate_invalid_credentials() -> None:
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    service = AuthService(db)
    with pytest.raises(HTTPException) as exc:
        await service.authenticate("user@example.com", "wrong")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_create_token_for_user() -> None:
    service = AuthService(AsyncMock())
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hashed",
    )
    token = service.create_token_for_user(user)
    assert isinstance(token, str)
    assert token
