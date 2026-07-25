"""Outbound email via Brevo HTTPS API (preferred) or Gmail SMTP fallback."""

from __future__ import annotations

import asyncio
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def smtp_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.smtp_username and settings.smtp_password)


def brevo_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.brevo_api_key.strip() and _from_address(settings))


def email_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return brevo_configured(settings) or smtp_configured(settings)


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
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(from_address, [to_email], message.as_string())


async def _send_brevo(
    *,
    settings: Settings,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    from_address = _from_address(settings)
    payload = {
        "sender": {
            "name": settings.smtp_from_name.strip() or "Agentic RAG",
            "email": from_address,
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": settings.brevo_api_key.strip(),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(BREVO_SEND_URL, headers=headers, json=payload)
    if response.status_code >= 400:
        detail = response.text[:300]
        logger.error(
            "brevo_send_failed",
            status_code=response.status_code,
            detail=detail,
        )
        raise RuntimeError(f"Brevo API {response.status_code}: {detail}")


async def _send_templated(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    settings: Settings,
) -> None:
    if not email_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Email verification is not configured. Set BREVO_API_KEY and "
                "SMTP_FROM_EMAIL (recommended on Railway), or SMTP_USERNAME and "
                "SMTP_PASSWORD for local Gmail SMTP."
            ),
        )
    try:
        if brevo_configured(settings):
            await _send_brevo(
                settings=settings,
                to_email=to_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
            return
        await asyncio.to_thread(
            _send_smtp,
            settings=settings,
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("email_send_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send email. Check email provider settings and try again.",
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
        "Enter this code in the app, or open this link to verify:\n"
        f"{verify_url}\n\n"
        f"This code expires in {expire_minutes} minutes.\n\n"
        "Thank you for reviewing my project. I hope you enjoy what I built.\n\n"
        "If you did not create an account, you can ignore this email.\n"
    )
    html_body = f"""\
<html>
  <body style="margin:0;padding:0;background:#f4f6f1;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" \
style="background:#f4f6f1;padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" \
style="max-width:480px;background:#ffffff;border-radius:14px;padding:28px 24px;\
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;\
color:#1a1f14;line-height:1.5;">
            <tr>
              <td style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;\
color:#6b7560;font-weight:600;padding-bottom:14px;">Agentic RAG</td>
            </tr>
            <tr>
              <td style="font-size:15px;padding-bottom:10px;">Hi,</td>
            </tr>
            <tr>
              <td style="font-size:15px;padding-bottom:18px;">
                Thanks for trying <strong>Agentic RAG</strong>, my personal portfolio demo.
              </td>
            </tr>
            <tr>
              <td style="font-size:14px;color:#4d5546;padding-bottom:8px;">
                Your verification code
              </td>
            </tr>
            <tr>
              <td style="font-size:28px;letter-spacing:0.18em;font-weight:700;\
font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;padding-bottom:12px;">
                {code}
              </td>
            </tr>
            <tr>
              <td style="font-size:14px;color:#4d5546;padding-bottom:16px;">
                Enter this code in the app, or click Continue to verify right away.
              </td>
            </tr>
            <tr>
              <td style="padding-bottom:18px;">
                <a href="{verify_url}" \
style="display:inline-block;background:#d8ff1a;color:#141a00;text-decoration:none;\
font-weight:700;font-size:15px;padding:12px 22px;border-radius:999px;">
                  Continue
                </a>
              </td>
            </tr>
            <tr>
              <td style="font-size:13px;color:#6b7560;padding-bottom:16px;">
                This code expires in {expire_minutes} minutes.
              </td>
            </tr>
            <tr>
              <td style="font-size:14px;padding-bottom:16px;">
                Thank you for reviewing my project. I hope you enjoy what I built.
              </td>
            </tr>
            <tr>
              <td style="font-size:12px;color:#8a9380;">
                If you did not create an account, you can ignore this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
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
