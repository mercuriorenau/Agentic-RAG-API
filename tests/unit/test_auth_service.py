from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.models import PendingSignup, User
from app.schemas.auth import UserRegister
from app.services.auth_service import AuthService


@pytest.mark.asyncio
@patch("app.services.auth_service.send_verification_email", new_callable=AsyncMock)
@patch("app.services.auth_service.email_configured", return_value=True)
async def test_register_creates_pending_signup(mock_smtp, mock_send) -> None:
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    service = AuthService(db)
    pending = await service.register(UserRegister(email="new@example.com", password="password123"))

    assert pending.email == "new@example.com"
    assert isinstance(pending, PendingSignup)
    db.add.assert_called_once()
    assert db.flush.await_count >= 1
    mock_send.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.services.auth_service.email_configured", return_value=False)
async def test_register_requires_smtp(mock_smtp) -> None:
    service = AuthService(AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await service.register(UserRegister(email="new@example.com", password="password123"))
    assert exc.value.status_code == 503


@pytest.mark.asyncio
@patch("app.services.auth_service.email_configured", return_value=True)
async def test_register_verified_email_raises_409(mock_smtp) -> None:
    existing = User(id=uuid4(), email="dup@example.com", hashed_password="x", email_verified=True)
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))

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
@patch("app.services.auth_service.verify_password", return_value=True)
async def test_authenticate_rejects_unverified(mock_verify) -> None:
    user = User(
        id=uuid4(),
        email="user@example.com",
        hashed_password="hashed",
        email_verified=False,
    )
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=user))

    service = AuthService(db)
    with pytest.raises(HTTPException) as exc:
        await service.authenticate("user@example.com", "password123")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_token_for_user() -> None:
    service = AuthService(AsyncMock())
    user = User(
        id=uuid4(),
        email="user@example.com",
        hashed_password="hashed",
        email_verified=True,
    )
    token = service.create_token_for_user(user)
    assert isinstance(token, str)
    assert token


@pytest.mark.asyncio
async def test_verify_email_code_success() -> None:
    code = "654321"
    user = User(
        id=uuid4(),
        email="user@example.com",
        hashed_password="hashed",
        email_verified=False,
        email_verify_code_hash=get_password_hash(code),
        email_verify_expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    db = AsyncMock()
    # pending lookup returns None, then user lookup returns user
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
    ]

    service = AuthService(db)
    verified = await service.verify_email_code("user@example.com", code)
    assert verified.email_verified is True
    assert verified.email_verify_code_hash is None


@pytest.mark.asyncio
@patch("app.services.auth_service.send_password_reset_email", new_callable=AsyncMock)
@patch("app.services.auth_service.email_configured", return_value=True)
async def test_password_reset_only_changes_after_code(mock_smtp, mock_send) -> None:
    from app.core.security import verify_password

    old_hash = get_password_hash("oldpass1")
    user = User(
        id=uuid4(),
        email="user@example.com",
        hashed_password=old_hash,
        email_verified=True,
    )
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=user))
    service = AuthService(db)

    await service.request_password_reset("user@example.com")
    assert user.password_reset_code_hash is not None
    assert user.hashed_password == old_hash
    mock_send.assert_awaited_once()

    code = mock_send.await_args.kwargs["code"]
    user.password_reset_code_hash = get_password_hash(code)
    user.password_reset_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    reset_user = await service.reset_password(
        email="user@example.com",
        code=code,
        new_password="newpass1",
    )
    assert reset_user.password_reset_code_hash is None
    assert verify_password("newpass1", reset_user.hashed_password)
    assert not verify_password("oldpass1", reset_user.hashed_password)