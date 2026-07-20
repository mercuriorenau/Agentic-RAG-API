from dataclasses import dataclass

from app.core.config import Settings

MODEL_MODES = {"auto", "openai", "anthropic"}

OPENAI_MODELS = (
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
)

ANTHROPIC_MODELS = (
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
)


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    mode: str
    provider: str | None
    model_name: str | None


@dataclass(frozen=True)
class ModelSelection:
    requested_mode: str
    provider: str
    model: str
    explanation: str


def list_available_models(settings: Settings) -> list[ModelOption]:
    options = [
        ModelOption(
            id="auto",
            label="Auto (inspect question, then choose)",
            mode="auto",
            provider=None,
            model_name=None,
        )
    ]

    if settings.openai_api_key:
        defaults = _unique([settings.chat_model, *OPENAI_MODELS])
        for model_name in defaults:
            options.append(
                ModelOption(
                    id=f"openai:{model_name}",
                    label=f"OpenAI · {model_name}",
                    mode="openai",
                    provider="openai",
                    model_name=model_name,
                )
            )

    if settings.anthropic_api_key:
        defaults = _unique([settings.anthropic_chat_model, *ANTHROPIC_MODELS])
        for model_name in defaults:
            options.append(
                ModelOption(
                    id=f"anthropic:{model_name}",
                    label=f"Anthropic · {model_name}",
                    mode="anthropic",
                    provider="anthropic",
                    model_name=model_name,
                )
            )

    return options


def select_model(
    question: str,
    settings: Settings,
    *,
    requested_mode: str = "auto",
    requested_model: str | None = None,
) -> ModelSelection:
    mode = requested_mode.lower().strip()
    if mode not in MODEL_MODES:
        mode = "auto"

    if mode == "openai":
        return ModelSelection(
            requested_mode=mode,
            provider="openai",
            model=_resolve_named_model(
                requested_model,
                settings.chat_model,
                OPENAI_MODELS,
            ),
            explanation=(
                "OpenAI was selected by the user. The agent will still decide whether "
                "to retrieve documents, search the web, or answer directly."
            ),
        )

    if mode == "anthropic":
        return ModelSelection(
            requested_mode=mode,
            provider="anthropic",
            model=_resolve_named_model(
                requested_model,
                settings.anthropic_chat_model,
                ANTHROPIC_MODELS,
            ),
            explanation=(
                "Anthropic was selected by the user. The agent will still decide whether "
                "to retrieve documents, search the web, or answer directly."
            ),
        )

    return _auto_select(question, settings)


def _auto_select(question: str, settings: Settings) -> ModelSelection:
    lowered = question.lower()
    signals: list[str] = []

    document_terms = ("document", "file", "uploaded", "policy", "contract", "pdf", "refund")
    current_terms = ("current", "today", "latest", "news", "now", "weather", "price")
    reasoning_terms = ("why", "how", "compare", "analyze", "explain", "tradeoff", "plan")

    if any(term in lowered for term in document_terms):
        signals.append("document-grounded wording")
    if any(term in lowered for term in current_terms):
        signals.append("current or external information wording")
    if any(term in lowered for term in reasoning_terms):
        signals.append("reasoning or explanation wording")

    if any(term in lowered for term in reasoning_terms) and settings.anthropic_api_key:
        provider = "anthropic"
        default_model = settings.anthropic_chat_model
        reason = "Anthropic was selected for a reasoning-heavy question."
    else:
        provider = "openai"
        default_model = settings.chat_model
        reason = "OpenAI was selected as the default agent model for retrieval and tool use."

    if provider == "openai" and not settings.openai_api_key and settings.anthropic_api_key:
        provider = "anthropic"
        default_model = settings.anthropic_chat_model
        reason = "Anthropic was selected because the OpenAI chat key is not configured."
    elif provider == "anthropic" and not settings.anthropic_api_key:
        provider = "openai"
        default_model = settings.chat_model
        reason = "OpenAI was selected because the Anthropic key is not configured."

    signal_text = ", ".join(signals) if signals else "no special routing signals"
    explanation = (
        f"Auto mode inspected the question before the agent call and found: {signal_text}. "
        f"{reason} After model selection, the agent separately chooses tools such as "
        "document retrieval, web search, or direct answer."
    )

    return ModelSelection(
        requested_mode="auto",
        provider=provider,
        model=default_model,
        explanation=explanation,
    )


def _resolve_named_model(
    requested_model: str | None,
    default_model: str,
    allowed: tuple[str, ...],
) -> str:
    model = (requested_model or "").strip()
    if not model:
        return default_model
    model = model[:80]
    allowed_set = {default_model, *allowed}
    if model in allowed_set:
        return model
    return default_model


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result
