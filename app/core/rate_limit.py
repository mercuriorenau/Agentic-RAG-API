from fastapi import Request
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address)


def bypass_emails() -> set[str]:
    settings = get_settings()
    return {
        part.strip().lower()
        for part in settings.rate_limit_bypass_emails.split(",")
        if part.strip()
    }


def email_from_auth_header(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None
    email = payload.get("email")
    return email.strip().lower() if isinstance(email, str) and email.strip() else None


def query_rate_limit_exempt(request: Request) -> bool:
    """Owner / manual Railway bypass for Ask (and the client lock that follows)."""
    settings = get_settings()
    if settings.rate_limit_disabled:
        return True
    allowed = bypass_emails()
    if not allowed:
        return False
    email = email_from_auth_header(request)
    return bool(email and email in allowed)


def user_is_rate_limit_exempt(email: str | None) -> bool:
    settings = get_settings()
    if settings.rate_limit_disabled:
        return True
    if not email:
        return False
    return email.strip().lower() in bypass_emails()
