import re


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def retrieval_relevance_score(
    retrieved_texts: list[str],
    expected_keywords: list[str],
) -> float:
    """Fraction of expected keywords that appear in any retrieved passage."""
    if not expected_keywords:
        return 1.0
    haystack = _normalize(" ".join(retrieved_texts))
    if not haystack:
        return 0.0
    hits = sum(1 for keyword in expected_keywords if keyword.lower() in haystack)
    return hits / len(expected_keywords)


def groundedness_score(answer: str, context_excerpts: list[str]) -> float:
    """
    Heuristic groundedness: overlap between answer content words and cited context.
    Returns 1.0 when there is no context (direct answers) and the answer is non-empty.
    """
    answer_tokens = _tokens(answer)
    if not answer_tokens:
        return 0.0
    if not context_excerpts:
        return 1.0

    context_tokens = _tokens(" ".join(context_excerpts))
    if not context_tokens:
        return 0.0

    overlap = answer_tokens & context_tokens
    return len(overlap) / len(answer_tokens)


def route_match(actual_route: str, expected_route: str) -> float:
    if actual_route == expected_route:
        return 1.0
    if actual_route == "mixed" and expected_route in {"retrieve", "web"}:
        return 0.5
    return 0.0
