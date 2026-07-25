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


def _client_ip(request: Request) -> str:
    """Prefer the real visitor IP behind Railway/proxies; fall back to peer address."""
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return get_remote_address(request)


def _jwt_claims(request: Request) -> dict:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return {}
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return {}
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return {}
    return payload if isinstance(payload, dict) else {}


def email_from_auth_header(request: Request) -> str | None:
    email = _jwt_claims(request).get("email")
    return email.strip().lower() if isinstance(email, str) and email.strip() else None


def query_rate_limit_key(request: Request) -> str:
    """
    Count Ask usage per signed-in user.

    IP-only keys are unreliable on Railway (proxy addresses / restarts), and
    clearing chat memory must not reset the daily Ask budget.
    """
    claims = _jwt_claims(request)
    subject = claims.get("sub")
    if isinstance(subject, str) and subject.strip():
        return f"user:{subject.strip()}"
    email = claims.get("email")
    if isinstance(email, str) and email.strip():
        return f"email:{email.strip().lower()}"
    return f"ip:{_client_ip(request)}"


def query_limit_value() -> str:
    return get_settings().rate_limit_query


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


# One shared daily budget for POST /queries and POST /queries/stream.
limit_ask = limiter.shared_limit(
    query_limit_value,
    scope="ask",
    key_func=query_rate_limit_key,
    exempt_when=query_rate_limit_exempt,
)
