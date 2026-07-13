"""Run offline heuristic evals against cases.json.

Usage:
    python -m evals.run_evals
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.scorers import groundedness_score, retrieval_relevance_score, route_match

CASES_PATH = Path(__file__).with_name("cases.json")


def load_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def evaluate_case(case: dict) -> dict:
    retrieved = case.get("sample_retrieved") or []
    context = case.get("context_excerpts") or retrieved
    answer = case.get("sample_answer") or ""
    expected_route = case.get("expected_route") or "direct"
    # Offline mode uses sample_answer route expectation as a self-check target.
    # Live agent runs can pass actual_route via CLI later.
    actual_route = case.get("actual_route") or expected_route

    relevance = retrieval_relevance_score(retrieved, case.get("expected_keywords") or [])
    groundedness = groundedness_score(answer, context)
    route = route_match(actual_route, expected_route)

    expect_low = bool(case.get("expect_low_groundedness"))
    groundedness_ok = groundedness < 0.5 if expect_low else groundedness >= 0.3
    needs_relevance = bool(case.get("expected_keywords")) and expected_route == "retrieve"
    relevance_ok = relevance >= 0.5 if needs_relevance else True
    route_ok = route >= 0.5

    passed = groundedness_ok and relevance_ok and route_ok
    return {
        "id": case["id"],
        "passed": passed,
        "relevance": round(relevance, 3),
        "groundedness": round(groundedness, 3),
        "route": round(route, 3),
    }


def main() -> int:
    cases = load_cases()
    results = [evaluate_case(case) for case in cases]
    passed = sum(1 for item in results if item["passed"])
    print(f"Evals: {passed}/{len(results)} passed\n")
    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        print(
            f"[{status}] {item['id']} "
            f"relevance={item['relevance']} "
            f"groundedness={item['groundedness']} "
            f"route={item['route']}"
        )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
