import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import PendingSignup, User
from app.schemas.auth import UserRegister
from app.services.email_service import (
    email_configured,
    send_password_reset_email,
    send_verification_email,
)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def register(self, data: UserRegister) -> PendingSignup:
        """Hold signup in pending_signups until the email code/link is verified.

        No row is written to ``users`` until verification succeeds. Re-registering
        the same unverified email only refreshes the pending row + sends a new code.
        """
        self._require_email()

        email = data.email.strip().lower()
        existing_user = await self._get_user_by_email(email)
        if existing_user is not None:
            if existing_user.email_verified or existing_user.google_sub:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )
            # Leftover unverified User from older flow; remove so email can pending-signup.
            await self.db.delete(existing_user)
            await self.db.flush()

        token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = datetime.now(UTC) + timedelta(
            minutes=self.settings.email_verification_expire_minutes
        )
        password_hash = get_password_hash(data.password)

        pending = await self._get_pending_by_email(email)
        if pending is None:
            pending = PendingSignup(
                id=uuid.uuid4(),
                email=email,
                hashed_password=password_hash,
                email_verify_token_hash=get_password_hash(token),
                email_verify_code_hash=get_password_hash(code),
                email_verify_expires_at=expires,
            )
            self.db.add(pending)
        else:
            pending.hashed_password = password_hash
            pending.email_verify_token_hash = get_password_hash(token)
            pending.email_verify_code_hash = get_password_hash(code)
            pending.email_verify_expires_at = expires

        await self.db.flush()
        try:
            await send_verification_email(
                to_email=email,
                verify_url=self.build_verify_url(token),
                code=code,
                settings=self.settings,
            )
        except Exception:
            await self.db.delete(pending)
            await self.db.flush()
            raise
        return pending

    async def authenticate(self, email: str, password: str) -> User:
        result = await self.db.execute(select(User).where(User.email == email.strip().lower()))
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
        if not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Please verify your email before signing in. "
                    "Check your inbox for the link or code."
                ),
            )
        return user

    async def upsert_google_user(self, *, email: str, google_sub: str) -> User:
        email = email.strip().lower()
        # Drop any pending email signup for this address; Google verifies ownership.
        pending = await self._get_pending_by_email(email)
        if pending is not None:
            await self.db.delete(pending)
            await self.db.flush()

        by_sub = await self.db.execute(select(User).where(User.google_sub == google_sub))
        user = by_sub.scalar_one_or_none()
        if user:
            if user.email != email:
                user.email = email
            user.email_verified = True
            self._clear_verification_secrets(user)
            self._clear_password_reset(user)
            await self.db.flush()
            return user

        by_email = await self.db.execute(select(User).where(User.email == email))
        user = by_email.scalar_one_or_none()
        if user:
            user.google_sub = google_sub
            user.email_verified = True
            self._clear_verification_secrets(user)
            self._clear_password_reset(user)
            await self.db.flush()
            return user

        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=None,
            google_sub=google_sub,
            email_verified=True,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def verify_email_token(self, token: str) -> User:
        token = token.strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing verification token",
            )
        pending = await self._find_pending_by_verify_token(token)
        if pending is not None:
            return await self._promote_pending(pending)

        user = await self._find_user_by_verify_token(token)
        self._mark_verified(user)
        await self.db.flush()
        return user

    async def verify_email_code(self, email: str, code: str) -> User:
        email = email.strip().lower()
        code = code.strip()
        pending = await self._get_pending_by_email(email)
        if pending is not None:
            self._assert_code_valid(
                code=code,
                code_hash=pending.email_verify_code_hash,
                expires_at=pending.email_verify_expires_at,
            )
            return await self._promote_pending(pending)

        user = await self._get_user_by_email(email)
        if not user or not user.email_verify_code_hash or not user.email_verify_expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )
        if user.email_verified:
            return user
        self._assert_code_valid(
            code=code,
            code_hash=user.email_verify_code_hash,
            expires_at=user.email_verify_expires_at,
        )
        self._mark_verified(user)
        await self.db.flush()
        return user

    async def resend_verification(self, email: str) -> None:
        """Always succeeds outwardly to avoid email enumeration."""
        self._require_email()
        email = email.strip().lower()
        pending = await self._get_pending_by_email(email)
        if pending is not None:
            await self._refresh_pending_verification(pending)
            return

        user = await self._get_user_by_email(email)
        if not user or user.email_verified or not user.hashed_password:
            return
        await self._issue_and_send_user_verification(user)

    async def request_password_reset(self, email: str) -> None:
        """Send a reset code. Does not change the password until the code is confirmed."""
        self._require_email()
        email = email.strip().lower()
        user = await self._get_user_by_email(email)
        # Only verified password accounts can reset. Always return quietly otherwise.
        if (
            not user
            or not user.email_verified
            or not user.hashed_password
        ):
            return

        code = f"{secrets.randbelow(1_000_000):06d}"
        user.password_reset_code_hash = get_password_hash(code)
        user.password_reset_expires_at = datetime.now(UTC) + timedelta(
            minutes=self.settings.email_verification_expire_minutes
        )
        await self.db.flush()
        try:
            await send_password_reset_email(
                to_email=user.email,
                code=code,
                settings=self.settings,
            )
        except Exception:
            # Roll back reset secrets so a failed send leaves the account unchanged.
            self._clear_password_reset(user)
            await self.db.flush()
            raise

    async def reset_password(self, *, email: str, code: str, new_password: str) -> User:
        email = email.strip().lower()
        user = await self._get_user_by_email(email)
        if (
            not user
            or not user.email_verified
            or not user.hashed_password
            or not user.password_reset_code_hash
            or not user.password_reset_expires_at
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset code",
            )
        self._assert_code_valid(
            code=code.strip(),
            code_hash=user.password_reset_code_hash,
            expires_at=user.password_reset_expires_at,
            invalid_detail="Invalid or expired reset code",
            expired_detail="Reset code expired. Request a new one.",
        )
        user.hashed_password = get_password_hash(new_password)
        self._clear_password_reset(user)
        await self.db.flush()
        return user

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    def create_token_for_user(self, user: User) -> str:
        return create_access_token(str(user.id), email=user.email)

    def build_verify_url(self, token: str) -> str:
        base = self.settings.app_public_url.rstrip("/")
        return f"{base}/api/v1/auth/verify-email?token={token}"

    def _require_email(self) -> None:
        if not email_configured(self.settings):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Email verification is not configured. Set BREVO_API_KEY and "
                    "SMTP_FROM_EMAIL (recommended on Railway), or SMTP_USERNAME and "
                    "SMTP_PASSWORD for local Gmail SMTP."
                ),
            )

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def _get_pending_by_email(self, email: str) -> PendingSignup | None:
        result = await self.db.execute(select(PendingSignup).where(PendingSignup.email == email))
        return result.scalar_one_or_none()

    async def _promote_pending(self, pending: PendingSignup) -> User:
        user = User(
            id=uuid.uuid4(),
            email=pending.email,
            hashed_password=pending.hashed_password,
            email_verified=True,
        )
        self.db.add(user)
        await self.db.delete(pending)
        await self.db.flush()
        return user

    async def _refresh_pending_verification(self, pending: PendingSignup) -> None:
        token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(1_000_000):06d}"
        pending.email_verify_token_hash = get_password_hash(token)
        pending.email_verify_code_hash = get_password_hash(code)
        pending.email_verify_expires_at = datetime.now(UTC) + timedelta(
            minutes=self.settings.email_verification_expire_minutes
        )
        await self.db.flush()
        await send_verification_email(
            to_email=pending.email,
            verify_url=self.build_verify_url(token),
            code=code,
            settings=self.settings,
        )

    async def _issue_and_send_user_verification(self, user: User) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(1_000_000):06d}"
        user.email_verify_token_hash = get_password_hash(token)
        user.email_verify_code_hash = get_password_hash(code)
        user.email_verify_expires_at = datetime.now(UTC) + timedelta(
            minutes=self.settings.email_verification_expire_minutes
        )
        user.email_verified = False
        await self.db.flush()
        await send_verification_email(
            to_email=user.email,
            verify_url=self.build_verify_url(token),
            code=code,
            settings=self.settings,
        )
        return token, code

    async def _find_pending_by_verify_token(self, token: str) -> PendingSignup | None:
        result = await self.db.execute(select(PendingSignup))
        now = datetime.now(UTC)
        for pending in result.scalars().all():
            expires = pending.email_verify_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires < now:
                continue
            if verify_password(token, pending.email_verify_token_hash):
                return pending
        return None

    async def _find_user_by_verify_token(self, token: str) -> User:
        result = await self.db.execute(
            select(User).where(
                User.email_verify_token_hash.is_not(None),
                User.email_verified.is_(False),
            )
        )
        candidates = list(result.scalars().all())
        now = datetime.now(UTC)
        for user in candidates:
            if not user.email_verify_token_hash or not user.email_verify_expires_at:
                continue
            expires = user.email_verify_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires < now:
                continue
            if verify_password(token, user.email_verify_token_hash):
                return user
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )

    def _assert_code_valid(
        self,
        *,
        code: str,
        code_hash: str,
        expires_at: datetime,
        invalid_detail: str = "Invalid or expired verification code",
        expired_detail: str = "Verification code expired. Request a new one.",
    ) -> None:
        expires = expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=expired_detail,
            )
        if not verify_password(code, code_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=invalid_detail,
            )

    def _mark_verified(self, user: User) -> None:
        user.email_verified = True
        self._clear_verification_secrets(user)

    @staticmethod
    def _clear_verification_secrets(user: User) -> None:
        user.email_verify_token_hash = None
        user.email_verify_code_hash = None
        user.email_verify_expires_at = None

    @staticmethod
    def _clear_password_reset(user: User) -> None:
        user.password_reset_code_hash = None
        user.password_reset_expires_at = None
