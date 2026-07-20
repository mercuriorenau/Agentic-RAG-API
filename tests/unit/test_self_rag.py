import pytest

from app.services.self_rag import needs_retry, parse_grade, parse_rewrite


def test_parse_grade_sufficient() -> None:
    assert parse_grade('{"grade": "sufficient", "reason": "clear answer"}') == "sufficient"


def test_parse_grade_partial_embedded() -> None:
    assert parse_grade('Grade result: {"grade": "partial", "reason": "thin"}') == "partial"


def test_parse_grade_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_grade('{"grade": "maybe"}')


def test_parse_rewrite() -> None:
    assert parse_rewrite('{"query": "Georgia Tech OMSCS recommendation letter"}') == (
        "Georgia Tech OMSCS recommendation letter"
    )


def test_needs_retry() -> None:
    assert needs_retry("irrelevant") is True
    assert needs_retry("partial") is True
    assert needs_retry("sufficient") is False
