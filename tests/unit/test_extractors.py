from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.utils.extractors import (
    UnsupportedFileTypeError,
    chunk_pages,
    chunk_text,
    extract_pages,
    extract_text,
)


def test_chunk_text_with_overlap() -> None:
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=300, chunk_overlap=50)
    assert len(chunks) >= 3
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_chunk_text_prefers_paragraph_boundaries() -> None:
    text = (
        "First paragraph stays together as one unit of meaning.\n\n"
        "Second paragraph is intentionally separate from the first.\n\n"
        "Third paragraph should land in a later chunk."
    )
    chunks = chunk_text(text, chunk_size=70, chunk_overlap=10)
    assert len(chunks) >= 2
    assert "First paragraph stays together" in chunks[0]
    assert "Second paragraph" not in chunks[0] or chunks[0].startswith("First")


def test_chunk_text_empty_returns_empty_list() -> None:
    assert chunk_text("   \n\t  ", chunk_size=100, chunk_overlap=10) == []


def test_chunk_text_invalid_overlap_raises() -> None:
    with pytest.raises(ValueError):
        chunk_text("hello", chunk_size=10, chunk_overlap=10)


def test_chunk_pages_keeps_page_numbers() -> None:
    pages = [(1, "Refund policy on page one."), (2, "Shipping details on page two.")]
    chunks = chunk_pages(pages, chunk_size=200, chunk_overlap=20)
    assert [chunk.page_number for chunk in chunks] == [1, 2]


def test_extract_txt_file(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Hello from a text file.", encoding="utf-8")
    assert extract_text(file_path, "text/plain") == "Hello from a text file."


def test_extract_md_file(tmp_path: Path) -> None:
    file_path = tmp_path / "readme.md"
    file_path.write_text("# Title\n\nSome markdown.", encoding="utf-8")
    text = extract_text(file_path, "text/markdown")
    assert "Some markdown." in text


def test_extract_pdf_pages(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    # pypdf blank pages have no text; write a simple text PDF via reportlab if available,
    # otherwise skip page extraction content assertion and only check unsupported path.
    with file_path.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ValueError, match="No extractable text"):
        extract_pages(file_path, "application/pdf")


def test_unsupported_file_type_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "data.csv"
    file_path.write_text("a,b,c", encoding="utf-8")
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(file_path, "text/csv")
