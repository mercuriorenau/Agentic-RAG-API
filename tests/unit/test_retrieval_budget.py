from app.core.config import Settings
from app.services.retrieval_budget import (
    query_looks_broad,
    query_looks_comparative,
    resolve_retrieval_budget,
    resolve_top_k,
)


def _settings(**overrides) -> Settings:
    base = {
        "top_k": 5,
        "top_k_max": 8,
        "adaptive_top_k": True,
    }
    base.update(overrides)
    return Settings(**base)


def test_focused_query_uses_base_top_k() -> None:
    budget = resolve_retrieval_budget("Caso 9 Waste Management", _settings())
    assert budget.top_k == 5
    assert budget.ideal_top_k == 5
    assert budget.capped is False
    assert resolve_top_k("Caso 9 Waste Management", _settings()) == 5


def test_user_question_each_case_is_broad_even_if_tool_query_is_narrow() -> None:
    """Budget must follow the user ask, not a short tool search string."""
    user_ask = "Describe shortly each case of the document"
    tool_query = "cases summary"
    assert query_looks_broad(user_ask)
    assert not query_looks_broad(tool_query)
    assert resolve_top_k(user_ask, _settings()) == 8
    assert resolve_top_k(tool_query, _settings()) == 5


def test_broad_query_uses_top_k_max_and_flags_cap() -> None:
    assert query_looks_broad("Dime de que trata cada caso de este documento")
    budget = resolve_retrieval_budget(
        "Dime de que trata cada caso de este documento", _settings()
    )
    assert budget.top_k == 8
    assert budget.ideal_top_k == 16
    assert budget.capped is True
    assert resolve_top_k("Summarize the document", _settings()) == 8


def test_comparative_query_uses_mid_budget() -> None:
    assert query_looks_comparative("Compare case 7 vs case 9")
    budget = resolve_retrieval_budget("Compare case 7 vs case 9", _settings())
    assert budget.top_k == 7
    assert budget.ideal_top_k == 7
    assert budget.capped is False


def test_comparative_capped_when_mid_exceeds_max() -> None:
    settings = _settings(top_k=7, top_k_max=8)
    budget = resolve_retrieval_budget("Compare case 7 vs case 9", settings)
    assert budget.top_k == 8
    assert budget.ideal_top_k == 9
    assert budget.capped is True


def test_adaptive_can_be_disabled() -> None:
    settings = _settings(adaptive_top_k=False, top_k=5, top_k_max=8)
    budget = resolve_retrieval_budget("list all cases in the document", settings)
    assert budget.top_k == 5
    assert budget.capped is False


def test_top_k_never_exceeds_max() -> None:
    settings = _settings(top_k=6, top_k_max=6, adaptive_top_k=True)
    assert resolve_top_k("overview of every case", settings) == 6
