from app.core.config import Settings, get_settings
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import LLMProvider
from app.services.llm.openai_provider import OpenAIProvider


def get_llm_provider(
    settings: Settings | None = None,
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
) -> LLMProvider:
    cfg = settings or get_settings()
    provider = (provider_name or cfg.llm_provider).lower().strip()
    if provider == "anthropic":
        return AnthropicProvider(cfg, model_name=model_name)
    if provider == "openai":
        return OpenAIProvider(cfg, model_name=model_name)
    raise ValueError(f"Unsupported LLM provider: {provider}")
