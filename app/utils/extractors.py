from pathlib import Path

from pypdf import PdfReader


class UnsupportedFileTypeError(ValueError):
    pass


def extract_text(file_path: Path, content_type: str) -> str:
    suffix = file_path.suffix.lower()

    if suffix == ".pdf" or content_type == "application/pdf":
        return _extract_pdf(file_path)
    if suffix in (".txt", ".md") or content_type in ("text/plain", "text/markdown"):
        return file_path.read_text(encoding="utf-8")
    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix or content_type}")


def _extract_pdf(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("No extractable text found in PDF")
    return text


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size")

    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = start + chunk_size
        chunks.append(normalized[start:end])
        if end >= len(normalized):
            break
        start = end - chunk_overlap
    return chunks
