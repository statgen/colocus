#!/bin/bash
set -e

# First run migrations and load data if needed
/opt/colocus/bin/entrypoint-migrate-and-load.sh

# Now run uvicorn
HOST=${UVICORN_HOST:-127.0.0.1}
PORT=${UVICORN_PORT:-8000}
WORKERS=${WEB_CONCURRENCY:-1}

uv run uvicorn config.asgi:application --host $HOST --port $PORT --workers $WORKERS "$@"
