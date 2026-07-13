from app.core.config import Settings
from app.services.llm.model_selector import list_available_models, select_model


def test_auto_prefers_anthropic_for_reasoning_when_configured() -> None:
    settings = Settings(openai_api_key="openai", anthropic_api_key="anthropic")

    selection = select_model("Explain the tradeoffs in this design.", settings)

    assert selection.provider == "anthropic"
    assert selection.model == settings.anthropic_chat_model
    assert "reasoning-heavy" in selection.explanation


def test_auto_uses_openai_default_for_retrieval_questions() -> None:
    settings = Settings(openai_api_key="openai", anthropic_api_key="anthropic")

    selection = select_model("What does the uploaded refund policy say?", settings)

    assert selection.provider == "openai"
    assert selection.model == settings.chat_model
    assert "document-grounded" in selection.explanation


def test_auto_falls_back_to_configured_provider_key() -> None:
    settings = Settings(openai_api_key="", anthropic_api_key="anthropic")

    selection = select_model("What does the file say?", settings)

    assert selection.provider == "anthropic"
    assert "OpenAI chat key is not configured" in selection.explanation


def test_user_selected_model_must_be_available() -> None:
    settings = Settings(openai_api_key="openai", chat_model="gpt-4o")

    selection = select_model(
        "hello",
        settings,
        requested_mode="openai",
        requested_model="not-a-real-model",
    )

    assert selection.provider == "openai"
    assert selection.model == "gpt-4o"


def test_list_available_models_respects_keys() -> None:
    settings = Settings(openai_api_key="openai", anthropic_api_key="")
    options = list_available_models(settings)

    assert options[0].id == "auto"
    assert any(option.id.startswith("openai:") for option in options)
    assert not any(option.id.startswith("anthropic:") for option in options)


def test_list_available_models_includes_anthropic_when_configured() -> None:
    settings = Settings(openai_api_key="openai", anthropic_api_key="anthropic")
    options = list_available_models(settings)

    assert any(option.id.startswith("openai:") for option in options)
    assert any(option.id.startswith("anthropic:") for option in options)
