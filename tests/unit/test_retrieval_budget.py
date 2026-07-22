from app.core.config import Settings
from app.services.retrieval_budget import (
    query_looks_broad,
    query_looks_comparative,
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
    assert resolve_top_k("Caso 9 Waste Management", _settings()) == 5


def test_broad_query_uses_top_k_max() -> None:
    assert query_looks_broad("Dime de que trata cada caso de este documento")
    assert resolve_top_k("Dime de que trata cada caso de este documento", _settings()) == 8
    assert resolve_top_k("Summarize the document", _settings()) == 8


def test_comparative_query_uses_mid_budget() -> None:
    assert query_looks_comparative("Compare case 7 vs case 9")
    assert resolve_top_k("Compare case 7 vs case 9", _settings()) == 7


def test_adaptive_can_be_disabled() -> None:
    settings = _settings(adaptive_top_k=False, top_k=5, top_k_max=8)
    assert resolve_top_k("list all cases in the document", settings) == 5


def test_top_k_never_exceeds_max() -> None:
    settings = _settings(top_k=6, top_k_max=6, adaptive_top_k=True)
    assert resolve_top_k("overview of every case", settings) == 6
