"""Sanitize and display document filenames (storage may use UUID paths)."""

from __future__ import annotations

import re
from pathlib import Path

_UUID_FILENAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"\.(pdf|txt|md)$",
    re.IGNORECASE,
)

_FRIENDLY_BY_EXT = {
    "pdf": "Uploaded PDF",
    "txt": "Uploaded text",
    "md": "Uploaded markdown",
}


def sanitize_upload_filename(filename: str | None) -> str:
    """Keep only the basename so path junk never lands in Document.filename."""
    name = Path(filename or "upload").name.strip() or "upload"
    return name[:255]


def display_document_name(filename: str | None) -> str:
    """Human label for UI/citations when the stored name is a bare UUID file."""
    name = (filename or "").strip() or "upload"
    match = _UUID_FILENAME.match(name)
    if not match:
        return name
    ext = match.group(1).lower()
    return _FRIENDLY_BY_EXT.get(ext, f"Uploaded {ext}")
