from app.core.config import Settings
from app.services.llm.model_selector import OPENAI_MODELS, list_available_models, select_model


def test_auto_prefers_anthropic_for_reasoning_when_configured() -> None:
    settings = Settings(openai_api_key="openai", anthropic_api_key="anthropic")

    selection = select_model("Explain the tradeoffs in this design.", settings)

    assert selection.provider == "anthropic"
    assert selection.model == settings.anthropic_chat_model
    assert "reasoning-heavy" in selection.explanation


def test_auto_prefers_anthropic_for_document_questions() -> None:
    settings = Settings(openai_api_key="openai", anthropic_api_key="anthropic")

    selection = select_model("What does the uploaded refund policy say?", settings)

    assert selection.provider == "anthropic"
    assert selection.model == settings.anthropic_chat_model
    assert "document-grounded" in selection.explanation


def test_auto_uses_openai_for_simple_non_document_questions() -> None:
    settings = Settings(
        openai_api_key="openai",
        anthropic_api_key="anthropic",
        chat_model="gpt-4.1",
    )

    selection = select_model("Say hello in one short sentence.", settings)

    assert selection.provider == "openai"
    assert selection.model == "gpt-4.1"


def test_auto_falls_back_to_configured_provider_key() -> None:
    settings = Settings(openai_api_key="", anthropic_api_key="anthropic")

    selection = select_model("What does the file say?", settings)

    assert selection.provider == "anthropic"
    assert selection.model == settings.anthropic_chat_model


def test_auto_falls_back_when_anthropic_missing() -> None:
    settings = Settings(
        openai_api_key="openai",
        anthropic_api_key="",
        chat_model="gpt-4.1",
    )

    selection = select_model("Explain the tradeoffs in this design.", settings)

    assert selection.provider == "openai"
    assert "Anthropic key is not configured" in selection.explanation


def test_user_selected_model_must_be_available() -> None:
    settings = Settings(openai_api_key="openai", chat_model="gpt-4.1")

    selection = select_model(
        "hello",
        settings,
        requested_mode="openai",
        requested_model="not-a-real-model",
    )

    assert selection.provider == "openai"
    assert selection.model == "gpt-4.1"


def test_list_available_models_respects_keys() -> None:
    settings = Settings(openai_api_key="openai", anthropic_api_key="", chat_model="gpt-4.1")
    options = list_available_models(settings)

    assert options[0].id == "auto"
    assert any(option.id.startswith("openai:") for option in options)
    assert not any(option.id.startswith("anthropic:") for option in options)


def test_list_available_models_uses_sonnet_peer_openai_tiers() -> None:
    settings = Settings(
        openai_api_key="openai",
        anthropic_api_key="anthropic",
        chat_model="gpt-4.1",
    )
    options = list_available_models(settings)
    openai_ids = [option.id for option in options if option.id.startswith("openai:")]

    assert OPENAI_MODELS == ("gpt-4.1", "gpt-5")
    assert any(option.id.startswith("anthropic:") for option in options)
    assert "openai:gpt-4.1" in openai_ids
    assert "openai:gpt-5" in openai_ids
    assert "openai:gpt-4o" not in openai_ids
    assert not any(option_id.endswith("mini") for option_id in openai_ids)
