from app.services.rerank_service import parse_index_list


def test_parse_index_list_complete() -> None:
    assert parse_index_list("[2, 0, 1]", expected=3) == [2, 0, 1]


def test_parse_index_list_fills_missing() -> None:
    assert parse_index_list("[1]", expected=3) == [1, 0, 2]


def test_parse_index_list_embedded_in_text() -> None:
    assert parse_index_list("Here you go: [0, 1]", expected=2) == [0, 1]
