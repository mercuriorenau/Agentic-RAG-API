from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_models_endpoint_lists_auto_option(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test")
    get_settings.cache_clear()

    client = TestClient(create_app())
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["models"][0]["id"] == "auto"
    assert any(item["id"].startswith("openai:") for item in body["models"])
    assert any(item["id"].startswith("anthropic:") for item in body["models"])
    get_settings.cache_clear()
