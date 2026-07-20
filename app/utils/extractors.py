from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


class UnsupportedFileTypeError(ValueError):
    pass


@dataclass(frozen=True)
class TextChunk:
    content: str
    page_number: int | None = None


def extract_text(file_path: Path, content_type: str) -> str:
    pages = extract_pages(file_path, content_type)
    text = "\n\n".join(content for _, content in pages).strip()
    if not text:
        raise ValueError("No extractable text found in document")
    return text


def extract_pages(file_path: Path, content_type: str) -> list[tuple[int | None, str]]:
    suffix = file_path.suffix.lower()

    if suffix == ".pdf" or content_type == "application/pdf":
        return _extract_pdf_pages(file_path)
    if suffix in (".txt", ".md") or content_type in ("text/plain", "text/markdown"):
        text = file_path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        return [(None, text)]
    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix or content_type}")


def _extract_pdf_pages(file_path: Path) -> list[tuple[int | None, str]]:
    reader = PdfReader(str(file_path))
    pages: list[tuple[int | None, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((index, text))
    if not pages:
        raise ValueError("No extractable text found in PDF")
    return pages


def chunk_pages(
    pages: list[tuple[int | None, str]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for page_number, text in pages:
        for content in chunk_text(text, chunk_size, chunk_overlap):
            chunks.append(TextChunk(content=content, page_number=page_number))
    return chunks


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size")

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        pieces = _split_oversized(paragraph, chunk_size)
        for piece in pieces:
            if not current:
                current = piece
                continue
            candidate = f"{current}\n\n{piece}"
            if len(candidate) <= chunk_size:
                current = candidate
                continue
            chunks.append(current)
            current = _overlap_prefix(current, chunk_overlap, piece, chunk_size)

    if current:
        chunks.append(current)
    return chunks


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n+", text.strip())
    return [" ".join(part.split()) for part in parts if part.strip()]


def _split_oversized(text: str, chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > chunk_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_hard_split(sentence, chunk_size))
            continue
        if not current:
            current = sentence
            continue
        candidate = f"{current} {sentence}"
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)
    return pieces


def _hard_split(text: str, chunk_size: int) -> list[str]:
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _overlap_prefix(
    previous: str,
    chunk_overlap: int,
    next_piece: str,
    chunk_size: int,
) -> str:
    if chunk_overlap <= 0:
        return next_piece
    room = chunk_size - len(next_piece) - 2
    if room <= 0:
        return next_piece
    take = min(chunk_overlap, room, len(previous))
    overlap = previous[-take:].strip()
    if not overlap:
        return next_piece
    candidate = f"{overlap}\n\n{next_piece}"
    if len(candidate) > chunk_size:
        return next_piece
    return candidate
