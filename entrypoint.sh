#!/bin/sh
set -e
alembic upgrade head
# Railway injects PORT at runtime; default 8000 for local Docker Compose.
PORT="${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
