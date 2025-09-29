#!/bin/bash
set -e

source .venv/bin/activate

# Function to check if migrations are needed
check_migrations_needed() {
  python3 manage.py showmigrations --plan | grep -q '\[ \]'
}

# Function to check if core app tables exist
check_core_tables_exist() {
    python3 -c "
import os
import django
from django.db import connections

# Check that django settings module is set
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
  raise EnvironmentError('DJANGO_SETTINGS_MODULE environment variable is not set; set before running container')

django.setup()

try:
  with connections['core'].cursor() as cursor:
    cursor.execute(\"SELECT COUNT(*) FROM core_datasubmission\")
    count = cursor.fetchone()[0]
    exit(0 if count > 0 else 1)
except Exception:
  exit(1)
"
}

# Check if core tables exist and migrations are up to date
if check_core_tables_exist && ! check_migrations_needed; then
  echo "Database already initialized and up to date"
else
  echo "Running database migrations..."
  python3 manage.py migrate
  python3 manage.py migrate --database=core

  # Only load dataset if it's a fresh database
  if ! check_core_tables_exist; then
    echo "Loading initial dataset..."
    python3 scripts/load_dataset.py /data
  fi
fi

# Now run uvicorn
HOST=${UVICORN_HOST:-127.0.0.1}
PORT=${UVICORN_PORT:-8000}
WORKERS=${WEB_CONCURRENCY:-1}
/opt/colocus/.venv/bin/uvicorn config.asgi:application --host $HOST --port $PORT --workers $WORKERS "$@"
