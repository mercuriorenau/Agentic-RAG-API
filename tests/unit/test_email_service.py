from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services import email_service


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "smtp_host": "smtp.test.local",
        "smtp_port": 587,
        "smtp_username": "smtp@test.local",
        "smtp_password": "secret",
        "smtp_from_email": "smtp@test.local",
        "smtp_from_name": "Agentic RAG",
        "brevo_api_key": "",
        "email_verification_expire_minutes": 10,
    }
    base.update(overrides)
    return Settings(**base)


def test_smtp_configured_requires_username_and_password() -> None:
    assert email_service.smtp_configured(_settings(smtp_password="")) is False
    assert email_service.smtp_configured(_settings()) is True


def test_email_configured_accepts_brevo_or_smtp() -> None:
    assert email_service.email_configured(_settings(smtp_username="", smtp_password="")) is False
    assert email_service.email_configured(
        _settings(
            smtp_username="",
            smtp_password="",
            brevo_api_key="xkeysib-test",
            smtp_from_email="from@test.local",
        )
    )
    assert email_service.email_configured(_settings())


def test_from_header_includes_display_name() -> None:
    header = email_service._from_header(_settings(smtp_from_name="Demo App"))
    assert "Demo App" in header
    assert "smtp@test.local" in header


@pytest.mark.asyncio
async def test_send_verification_email_prefers_brevo() -> None:
    settings = _settings(brevo_api_key="xkeysib-test")
    with patch("app.services.email_service._send_brevo", new_callable=AsyncMock) as mock_brevo:
        with patch("app.services.email_service._send_smtp") as mock_smtp:
            await email_service.send_verification_email(
                to_email="user@example.com",
                verify_url="http://test/api/v1/auth/verify-email?token=abc",
                code="123456",
                settings=settings,
            )
    mock_brevo.assert_awaited_once()
    mock_smtp.assert_not_called()
    kwargs = mock_brevo.await_args.kwargs
    assert kwargs["to_email"] == "user@example.com"
    assert "123456" in kwargs["text_body"]
    assert "token=abc" in kwargs["html_body"]


@pytest.mark.asyncio
async def test_send_verification_email_uses_smtp_without_brevo() -> None:
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
async def test_send_templated_requires_email_provider() -> None:
    settings = _settings(smtp_username="", smtp_password="", brevo_api_key="")
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


@pytest.mark.asyncio
async def test_send_brevo_posts_transactional_email() -> None:
    settings = _settings(brevo_api_key="xkeysib-test", smtp_from_email="from@test.local")
    response = MagicMock()
    response.status_code = 201
    response.text = '{"messageId":"1"}'
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.email_service.httpx.AsyncClient", return_value=client):
        await email_service._send_brevo(
            settings=settings,
            to_email="user@example.com",
            subject="Subject",
            text_body="plain",
            html_body="<p>html</p>",
        )
    client.post.assert_awaited_once()
    args, kwargs = client.post.await_args
    assert args[0] == email_service.BREVO_SEND_URL
    assert kwargs["headers"]["api-key"] == "xkeysib-test"
    assert kwargs["json"]["sender"]["email"] == "from@test.local"
    assert kwargs["json"]["to"] == [{"email": "user@example.com"}]


@pytest.mark.asyncio
async def test_send_brevo_raises_on_api_error() -> None:
    settings = _settings(brevo_api_key="xkeysib-test", smtp_from_email="from@test.local")
    response = MagicMock()
    response.status_code = 401
    response.text = "unauthorized"
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.email_service.httpx.AsyncClient", return_value=client):
        with pytest.raises(RuntimeError, match="Brevo API 401"):
            await email_service._send_brevo(
                settings=settings,
                to_email="user@example.com",
                subject="Subject",
                text_body="plain",
                html_body="<p>html</p>",
            )


def test_settings_strips_spaces_from_gmail_app_password() -> None:
    settings = Settings(
        smtp_username="user@gmail.com",
        smtp_password="abcd efgh ijkl mnop",
        smtp_from_email="user@gmail.com",
    )
    assert settings.smtp_password == "abcdefghijklmnop"
