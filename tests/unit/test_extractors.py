from pathlib import Path

import pytest

from app.utils.extractors import UnsupportedFileTypeError, chunk_text, extract_text


def test_chunk_text_with_overlap() -> None:
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=300, chunk_overlap=50)
    assert len(chunks) >= 3
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_chunk_text_empty_returns_empty_list() -> None:
    assert chunk_text("   \n\t  ", chunk_size=100, chunk_overlap=10) == []


def test_chunk_text_invalid_overlap_raises() -> None:
    with pytest.raises(ValueError):
        chunk_text("hello", chunk_size=10, chunk_overlap=10)


def test_extract_txt_file(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Hello from a text file.", encoding="utf-8")
    assert extract_text(file_path, "text/plain") == "Hello from a text file."


def test_extract_md_file(tmp_path: Path) -> None:
    file_path = tmp_path / "readme.md"
    file_path.write_text("# Title\n\nSome markdown.", encoding="utf-8")
    text = extract_text(file_path, "text/markdown")
    assert "Some markdown." in text


def test_unsupported_file_type_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "data.csv"
    file_path.write_text("a,b,c", encoding="utf-8")
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(file_path, "text/csv")
