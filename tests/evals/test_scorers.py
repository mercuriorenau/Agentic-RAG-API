import json
from pathlib import Path

from evals.run_evals import evaluate_case, load_cases
from evals.scorers import groundedness_score, retrieval_relevance_score, route_match


def test_retrieval_relevance_partial_match() -> None:
    score = retrieval_relevance_score(
        ["Refund within 30 days of purchase."],
        ["refund", "30", "days", "missing"],
    )
    assert 0.7 <= score <= 0.8


def test_retrieval_relevance_empty_keywords() -> None:
    assert retrieval_relevance_score([], []) == 1.0


def test_groundedness_with_overlap() -> None:
    score = groundedness_score(
        "Returns are allowed within 30 days.",
        ["Our refund policy allows returns within 30 days of purchase."],
    )
    assert score >= 0.4


def test_groundedness_hallucination_low() -> None:
    score = groundedness_score(
        "The warranty lasts forever with free replacements for life.",
        ["Products include a 12-month limited warranty."],
    )
    assert score < 0.5


def test_route_match() -> None:
    assert route_match("retrieve", "retrieve") == 1.0
    assert route_match("mixed", "retrieve") == 0.5
    assert route_match("direct", "web") == 0.0


def test_cases_file_loads() -> None:
    cases = load_cases()
    assert len(cases) >= 9
    assert Path("evals/cases.json").exists()
    assert Path("evals/fixtures/policy.md").exists()


def test_offline_eval_suite_passes() -> None:
    results = [evaluate_case(case) for case in load_cases()]
    assert all(item["passed"] for item in results)


def test_cases_json_is_valid() -> None:
    raw = Path("evals/cases.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, list)
    for case in data:
        assert "id" in case
        assert "question" in case
        assert "expected_route" in case
        assert "fixtures" in case


def test_run_evals_offline_cli() -> None:
    from evals.run_evals import main

    assert main([]) == 0
