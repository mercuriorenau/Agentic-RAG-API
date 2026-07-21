import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.api.deps import get_auth_service
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth_service import AuthService
from app.services.google_oauth import (
    build_google_authorize_url,
    exchange_code_for_userinfo,
    google_oauth_configured,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(get_settings().rate_limit_auth)
async def register(
    request: Request,
    data: UserRegister,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    user = await auth_service.register(data)
    return UserResponse(id=str(user.id), email=user.email)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_settings().rate_limit_auth)
async def login(
    request: Request,
    data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user = await auth_service.authenticate(data.email, data.password)
    token = auth_service.create_token_for_user(user)
    return TokenResponse(access_token=token)


@router.get("/google")
@limiter.limit(get_settings().rate_limit_auth)
async def google_login_start(request: Request) -> RedirectResponse:
    settings = get_settings()
    if not google_oauth_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(url=build_google_authorize_url(settings, state=state))
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=600,
        secure=settings.app_public_url.startswith("https://"),
    )
    return response


@router.get("/google/callback")
@limiter.limit(get_settings().rate_limit_auth)
async def google_login_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    settings = get_settings()
    if error:
        return _frontend_redirect(settings, error="Google sign-in was cancelled or denied")
    if not code or not state:
        return _frontend_redirect(settings, error="Missing Google authorization code")

    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or cookie_state != state:
        return _frontend_redirect(settings, error="Invalid Google sign-in state")

    try:
        profile = await exchange_code_for_userinfo(settings, code)
        user = await auth_service.upsert_google_user(
            email=profile["email"],
            google_sub=profile["google_sub"],
        )
        token = auth_service.create_token_for_user(user)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Google sign-in failed"
        return _frontend_redirect(settings, error=detail)

    response = _frontend_redirect(
        settings,
        token=token,
        email=user.email,
    )
    response.delete_cookie("oauth_state")
    return response


def _frontend_redirect(
    settings,
    *,
    token: str | None = None,
    email: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    params: dict[str, str] = {}
    if token:
        params["auth_token"] = token
    if email:
        params["auth_email"] = email
    if error:
        params["auth_error"] = error
    query = f"?{urlencode(params)}" if params else ""
    response = RedirectResponse(url=f"{settings.app_public_url.rstrip('/')}{query}")
    return response
