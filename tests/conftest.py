import os
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.main import create_app
from app.models import Base
from tests.email_outbox import verification_outbox

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ragdb_test",
)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def test_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("SMTP_USERNAME", "smtp@test.local")
    monkeypatch.setenv("SMTP_PASSWORD", "test-app-password")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "smtp@test.local")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://test")
    monkeypatch.setenv("RATE_LIMIT_AUTH", "1000/minute")
    monkeypatch.setenv("RATE_LIMIT_QUERY", "1000/minute")
    get_settings.cache_clear()
    return get_settings()


@pytest_asyncio.fixture
async def db_engine(test_settings):
    engine = create_async_engine(test_settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
            await conn.run_sync(Base.metadata.create_all)
    except (OSError, ConnectionRefusedError, Exception) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL not available: {exc}")

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_engine, test_settings, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    verification_outbox.clear()
    limiter.enabled = False

    async def fake_send_verification_email(
        *,
        to_email: str,
        verify_url: str,
        code: str,
        settings=None,
    ) -> None:
        token = parse_qs(urlparse(verify_url).query).get("token", [""])[0]
        verification_outbox.update(
            {
                "email": to_email,
                "code": code,
                "token": token,
                "verify_url": verify_url,
                "kind": "verify",
            }
        )

    async def fake_send_password_reset_email(
        *,
        to_email: str,
        code: str,
        settings=None,
    ) -> None:
        verification_outbox.update(
            {
                "email": to_email,
                "code": code,
                "token": None,
                "verify_url": None,
                "kind": "reset",
            }
        )

    monkeypatch.setattr(
        "app.services.auth_service.send_verification_email",
        fake_send_verification_email,
    )
    monkeypatch.setattr(
        "app.services.auth_service.send_password_reset_email",
        fake_send_password_reset_email,
    )

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.state.limiter = limiter
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    limiter.enabled = True
    get_settings.cache_clear()
    verification_outbox.clear()
