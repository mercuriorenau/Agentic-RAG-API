#!/bin/sh
set -e

echo "entrypoint: running alembic upgrade head"
alembic upgrade head
echo "entrypoint: migrations ok"

# Railway injects PORT at runtime; default 8000 for local Docker Compose.
PORT="${PORT:-8000}"
echo "entrypoint: starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
