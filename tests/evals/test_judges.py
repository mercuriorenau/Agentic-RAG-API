from evals.judges import parse_judge_scores


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
