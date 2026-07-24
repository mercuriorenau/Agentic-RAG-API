from unittest.mock import MagicMock

from app.core.rate_limit import query_rate_limit_exempt, user_is_rate_limit_exempt
from app.core.security import create_access_token


def test_user_is_rate_limit_exempt_by_email(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_BYPASS_EMAILS", "owner@example.com, other@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert user_is_rate_limit_exempt("owner@example.com") is True
    assert user_is_rate_limit_exempt("visitor@example.com") is False
    get_settings.cache_clear()


def test_user_is_rate_limit_exempt_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_BYPASS_EMAILS", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert user_is_rate_limit_exempt("anyone@example.com") is True
    get_settings.cache_clear()


def test_query_rate_limit_exempt_from_jwt_email(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_BYPASS_EMAILS", "owner@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    token = create_access_token("user-id", email="owner@example.com")
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    assert query_rate_limit_exempt(request) is True

    request.headers = {"Authorization": f"Bearer {create_access_token('x', email='nope@example.com')}"}
    assert query_rate_limit_exempt(request) is False
    get_settings.cache_clear()
