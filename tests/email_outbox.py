"""Shared SMTP/test outbox; imported by conftest and tests (avoid dual conftest modules)."""

from typing import Any

verification_outbox: dict[str, Any] = {}
