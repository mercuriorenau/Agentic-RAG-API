from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


def test_password_hashing_roundtrip() -> None:
    hashed = get_password_hash("securepassword")
    assert hashed != "securepassword"
    assert verify_password("securepassword", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_create_and_decode_access_token() -> None:
    token = create_access_token("user-123", expires_delta=timedelta(minutes=5))
    subject = decode_access_token(token)
    assert subject == "user-123"


def test_decode_invalid_token_returns_none() -> None:
    assert decode_access_token("not-a-valid-token") is None
