from fastapi import APIRouter, Depends, Request

from app.api.deps import get_auth_service
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth_service import AuthService

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
