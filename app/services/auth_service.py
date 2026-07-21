import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import User
from app.schemas.auth import UserRegister


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, data: UserRegister) -> User:
        existing = await self.db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = User(
            id=uuid.uuid4(),
            email=data.email,
            hashed_password=get_password_hash(data.password),
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def authenticate(self, email: str, password: str) -> User:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if (
            not user
            or not user.hashed_password
            or not verify_password(password, user.hashed_password)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        return user

    async def upsert_google_user(self, *, email: str, google_sub: str) -> User:
        by_sub = await self.db.execute(select(User).where(User.google_sub == google_sub))
        user = by_sub.scalar_one_or_none()
        if user:
            if user.email != email:
                user.email = email
                await self.db.flush()
            return user

        by_email = await self.db.execute(select(User).where(User.email == email))
        user = by_email.scalar_one_or_none()
        if user:
            user.google_sub = google_sub
            await self.db.flush()
            return user

        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=None,
            google_sub=google_sub,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    def create_token_for_user(self, user: User) -> str:
        return create_access_token(str(user.id))
