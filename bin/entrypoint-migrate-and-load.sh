#!/bin/bash
set -e

source .venv/bin/activate

# Function to check if migrations are needed
check_migrations_needed() {
  uv run python3 manage.py showmigrations --plan | grep -q '\[ \]'
}

# Function to check if core app tables exist
check_core_tables_exist() {
    uv run python3 -c "
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
  uv run python3 manage.py migrate
  uv run python3 manage.py migrate --database=core

  # Only load datasets if it's a fresh database
  if ! check_core_tables_exist; then
    echo "Loading initial dataset(s)..."
    for subdir in `find /data -type d -mindepth 1 -maxdepth 1`
    do
      # Remove the trailing slash
      subdir="${subdir%/}"
      if [ -d "$subdir" ]; then
        # Load dataset
        uv run python3 scripts/load_dataset.py "${subdir}"
      fi
    done
  fi
fi
