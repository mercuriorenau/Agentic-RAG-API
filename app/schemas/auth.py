from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=5, max_length=20)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class EmailOnlyRequest(BaseModel):
    email: EmailStr


class VerifyEmailCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=5, max_length=20)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    detail: str


class UserResponse(BaseModel):
    id: str
    email: str
    email_verified: bool = False
    rate_limit_exempt: bool = False
    onboarded: bool = False

    model_config = {"from_attributes": True}
