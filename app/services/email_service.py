"""Outbound email via Gmail SMTP (App Password)."""

from __future__ import annotations

import asyncio
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def smtp_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.smtp_username and settings.smtp_password)


def _from_address(settings: Settings) -> str:
    return (settings.smtp_from_email or settings.smtp_username).strip()


def _from_header(settings: Settings) -> str:
    address = _from_address(settings)
    name = settings.smtp_from_name.strip()
    if name:
        return formataddr((name, address))
    return address


def _send_smtp(
    *,
    settings: Settings,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    from_address = _from_address(settings)
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = _from_header(settings)
    message["To"] = to_email
    message["Reply-To"] = from_address
    message["Date"] = formatdate(localtime=False)
    domain = from_address.split("@")[-1] if "@" in from_address else "localhost"
    message["Message-ID"] = make_msgid(domain=domain, idstring=uuid.uuid4().hex[:12])
    message["Auto-Submitted"] = "auto-generated"
    message["X-Auto-Response-Suppress"] = "All"
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(from_address, [to_email], message.as_string())


async def _send_templated(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    settings: Settings,
) -> None:
    if not smtp_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Email verification is not configured. Set SMTP_USERNAME and "
                "SMTP_PASSWORD (Gmail App Password) on the server."
            ),
        )
    try:
        await asyncio.to_thread(
            _send_smtp,
            settings=settings,
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    except Exception as exc:
        logger.exception("smtp_send_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send email. Check SMTP settings and try again.",
        ) from exc


async def send_verification_email(
    *,
    to_email: str,
    verify_url: str,
    code: str,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    expire_minutes = settings.email_verification_expire_minutes
    subject = f"Your verification code is {code}"
    text_body = (
        "Hi,\n\n"
        "Thanks for trying Agentic RAG (my personal portfolio demo).\n\n"
        f"Your verification code is: {code}\n\n"
        f"You can also open this link to verify:\n{verify_url}\n\n"
        f"This code expires in {expire_minutes} minutes.\n\n"
        "Thank you for reviewing my project. I hope you enjoy what I built.\n\n"
        "If you did not create an account, you can ignore this email.\n"
    )
    html_body = f"""\
<html>
  <body style="font-family: Georgia, 'Times New Roman', serif; color: #222; line-height: 1.5;">
    <p>Hi,</p>
    <p>Thanks for trying <strong>Agentic RAG</strong> (my personal portfolio demo).</p>
    <p>Your verification code is:</p>
    <p style="font-size:1.35rem;letter-spacing:0.12em;\
font-weight:700;font-family:ui-monospace,monospace;">{code}</p>
    <p>
      Or verify with this link:<br/>
      <a href="{verify_url}">{verify_url}</a>
    </p>
    <p>This code expires in {expire_minutes} minutes.</p>
    <p>Thank you for reviewing my project. I hope you enjoy what I built.</p>
    <p style="color:#666;font-size:0.92rem;">
      If you did not create an account, you can ignore this email.
    </p>
  </body>
</html>
"""
    await _send_templated(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        settings=settings,
    )


async def send_password_reset_email(
    *,
    to_email: str,
    code: str,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    expire_minutes = settings.email_verification_expire_minutes
    subject = f"Your password reset code is {code}"
    text_body = (
        "Hi,\n\n"
        "We received a request to reset your Agentic RAG password.\n\n"
        f"Your reset code is: {code}\n\n"
        f"This code expires in {expire_minutes} minutes.\n\n"
        "If you did not request a password reset, you can ignore this email. "
        "Your password will stay the same.\n"
    )
    html_body = f"""\
<html>
  <body style="font-family: Georgia, 'Times New Roman', serif; color: #222; line-height: 1.5;">
    <p>Hi,</p>
    <p>We received a request to reset your <strong>Agentic RAG</strong> password.</p>
    <p>Your reset code is:</p>
    <p style="font-size:1.35rem;letter-spacing:0.12em;\
font-weight:700;font-family:ui-monospace,monospace;">{code}</p>
    <p>This code expires in {expire_minutes} minutes.</p>
    <p style="color:#666;font-size:0.92rem;">
      If you did not request a password reset, ignore this email. Your password will stay the same.
    </p>
  </body>
</html>
"""
    await _send_templated(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        settings=settings,
    )
