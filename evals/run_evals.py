"""Run offline heuristic evals against cases.json, or live RAG evals with --live.

Usage:
    python -m evals.run_evals
    python -m evals.run_evals --live
    python -m evals.run_evals --live --judge
"""

from __future__ import annotations

import argparse
import asyncio
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
    actual_route = case.get("actual_route") or expected_route

    relevance = retrieval_relevance_score(retrieved, case.get("expected_keywords") or [])
    groundedness = groundedness_score(answer, context)
    route = route_match(actual_route, expected_route)

    expect_low = bool(case.get("expect_low_groundedness"))
    groundedness_ok = groundedness < 0.5 if expect_low else groundedness >= 0.3
    needs_relevance = bool(case.get("expected_keywords")) and expected_route == "retrieve"
    relevance_ok = relevance >= 0.5 if needs_relevance else True
    route_ok = route >= 0.5

    if case.get("expect_empty_retrieve") and case.get("mode") != "live":
        relevance_ok = len(retrieved) == 0
        groundedness_ok = True
        route_ok = True

    passed = groundedness_ok and relevance_ok and route_ok
    return {
        "id": case["id"],
        "passed": passed,
        "relevance": round(relevance, 3),
        "groundedness": round(groundedness, 3),
        "route": round(route, 3),
        "_question": case.get("question") or "",
        "_answer": answer,
        "_context": context,
        "_expect_low": expect_low,
    }


async def _attach_judge_scores(results: list[dict]) -> list[dict]:
    from evals.judges import judge_answer

    enriched: list[dict] = []
    for item in results:
        row = {k: v for k, v in item.items() if not k.startswith("_")}
        if item.get("_expect_low"):
            row["faithfulness"] = None
            row["answer_relevance"] = None
            enriched.append(row)
            continue

        scores = await judge_answer(
            item.get("_question") or "",
            item.get("_answer") or "",
            item.get("_context") or [],
        )
        faithfulness = scores["faithfulness"]
        answer_relevance = scores["answer_relevance"]
        row["faithfulness"] = round(faithfulness, 3)
        row["answer_relevance"] = round(answer_relevance, 3)
        row["passed"] = bool(row["passed"]) and faithfulness >= 0.5 and answer_relevance >= 0.5
        enriched.append(row)
    return enriched


def _print_results(results: list[dict], label: str) -> int:
    passed = sum(1 for item in results if item["passed"])
    print(f"{label}: {passed}/{len(results)} passed\n")
    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        extra = ""
        if "retrieved_count" in item:
            extra += f" retrieved={item['retrieved_count']}"
        if item.get("faithfulness") is not None:
            extra += (
                f" faithfulness={item['faithfulness']}"
                f" answer_relevance={item['answer_relevance']}"
            )
        print(
            f"[{status}] {item['id']} "
            f"relevance={item['relevance']} "
            f"groundedness={item['groundedness']} "
            f"route={item['route']}{extra}"
        )
    return 0 if passed == len(results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run RAG evals")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Seed fixtures and score against the real retrieve (+ agent) path",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Add LLM-as-judge faithfulness / answer_relevance scores (needs OPENAI_API_KEY)",
    )
    args = parser.parse_args(argv)
    cases = load_cases()

    if args.live:
        from evals.live_runner import run_live_evals

        results = asyncio.run(run_live_evals(cases, evaluate_case))
        label = "Live evals"
    else:
        results = [evaluate_case(case) for case in cases]
        label = "Evals"

    if args.judge:
        results = asyncio.run(_attach_judge_scores(results))
        label = f"{label} + judge"

    # Strip private keys before print/return bookkeeping
    cleaned = [{k: v for k, v in item.items() if not k.startswith("_")} for item in results]
    return _print_results(cleaned, label)


if __name__ == "__main__":
    sys.exit(main())
