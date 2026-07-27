import asyncio

from evals.judges import parse_judge_scores
from evals.run_evals import _attach_judge_scores, evaluate_case, load_cases


def test_parse_judge_scores() -> None:
    scores = parse_judge_scores(
        '{"faithfulness": 0.9, "answer_relevance": 0.8}'
    )
    assert scores["faithfulness"] == 0.9
    assert scores["answer_relevance"] == 0.8


def test_parse_judge_scores_clamps() -> None:
    scores = parse_judge_scores('{"faithfulness": 1.5, "answer_relevance": -0.2}')
    assert scores["faithfulness"] == 1.0
    assert scores["answer_relevance"] == 0.0


def test_empty_retrieve_case_skips_judge() -> None:
    case = next(c for c in load_cases() if c["id"] == "retrieve_no_relevant")
    scored = evaluate_case(case)
    assert scored["_skip_judge"] is True

    enriched = asyncio.run(_attach_judge_scores([scored]))
    assert enriched[0]["passed"] is True
    assert enriched[0]["faithfulness"] is None
    assert enriched[0]["answer_relevance"] is None
