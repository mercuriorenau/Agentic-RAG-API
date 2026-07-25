from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services import email_service


def _settings(**overrides: str) -> Settings:
    base = {
        "smtp_host": "smtp.test.local",
        "smtp_port": 587,
        "smtp_username": "smtp@test.local",
        "smtp_password": "secret",
        "smtp_from_email": "smtp@test.local",
        "smtp_from_name": "Agentic RAG",
        "email_verification_expire_minutes": 10,
    }
    base.update(overrides)
    return Settings(**base)


def test_smtp_configured_requires_username_and_password() -> None:
    assert email_service.smtp_configured(_settings(smtp_password="")) is False
    assert email_service.smtp_configured(_settings()) is True


def test_from_header_includes_display_name() -> None:
    header = email_service._from_header(_settings(smtp_from_name="Demo App"))
    assert "Demo App" in header
    assert "smtp@test.local" in header


@pytest.mark.asyncio
async def test_send_verification_email_uses_smtp() -> None:
    settings = _settings()
    with patch("app.services.email_service._send_smtp") as mock_send:
        await email_service.send_verification_email(
            to_email="user@example.com",
            verify_url="http://test/api/v1/auth/verify-email?token=abc",
            code="123456",
            settings=settings,
        )
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to_email"] == "user@example.com"
    assert "123456" in kwargs["text_body"]
    assert "123456" in kwargs["html_body"]
    assert "token=abc" in kwargs["html_body"]


@pytest.mark.asyncio
async def test_send_password_reset_email_uses_smtp() -> None:
    settings = _settings()
    with patch("app.services.email_service._send_smtp") as mock_send:
        await email_service.send_password_reset_email(
            to_email="user@example.com",
            code="654321",
            settings=settings,
        )
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert "654321" in kwargs["text_body"]
    assert "reset" in kwargs["subject"].lower()


@pytest.mark.asyncio
async def test_send_templated_requires_smtp() -> None:
    settings = _settings(smtp_username="", smtp_password="")
    with pytest.raises(HTTPException) as exc:
        await email_service._send_templated(
            to_email="user@example.com",
            subject="Hi",
            text_body="body",
            html_body="<p>body</p>",
            settings=settings,
        )
    assert exc.value.status_code == 503


def test_send_smtp_logs_in_and_sends() -> None:
    settings = _settings()
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.__exit__.return_value = False
    with patch("app.services.email_service.smtplib.SMTP", return_value=smtp) as smtp_cls:
        email_service._send_smtp(
            settings=settings,
            to_email="user@example.com",
            subject="Subject",
            text_body="plain",
            html_body="<p>html</p>",
        )
    smtp_cls.assert_called_once_with(settings.smtp_host, settings.smtp_port, timeout=30)
    assert smtp.ehlo.call_count == 2
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with(settings.smtp_username, settings.smtp_password)
    smtp.sendmail.assert_called_once()


def test_settings_strips_spaces_from_gmail_app_password() -> None:
    settings = Settings(
        smtp_username="user@gmail.com",
        smtp_password="abcd efgh ijkl mnop",
        smtp_from_email="user@gmail.com",
    )
    assert settings.smtp_password == "abcdefghijklmnop"
