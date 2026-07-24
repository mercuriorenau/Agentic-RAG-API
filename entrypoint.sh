#!/bin/sh
set -e

PORT="${PORT:-8000}"

echo "entrypoint: PORT=${PORT}"
if [ -z "${DATABASE_URL:-}" ]; then
  echo "entrypoint: ERROR DATABASE_URL is not set" >&2
  exit 1
fi
# Redact credentials; show only scheme/host for debugging.
echo "entrypoint: DATABASE_URL scheme/host=$(echo "$DATABASE_URL" | sed -E 's#://[^@/]+@#://***@#; s#(\\?.*)$##')"

echo "entrypoint: running alembic upgrade head"
if ! alembic upgrade head; then
  echo "entrypoint: ERROR alembic failed." >&2
  echo "entrypoint: If you see 'extension \"vector\" is not available', replace Railway's" >&2
  echo "entrypoint: plain Postgres with a **pgvector** template and re-link DATABASE_URL." >&2
  exit 1
fi
echo "entrypoint: migrations ok"

echo "entrypoint: starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
