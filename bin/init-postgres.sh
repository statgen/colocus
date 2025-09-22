#!/bin/bash
set -e

# Check if database exists before creating
if ! psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$POSTGRES_DB_CORE"; then
  psql -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB_CORE;"
fi

if ! psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$POSTGRES_DB_DEFAULT"; then
  psql -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB_DEFAULT;"
fi

# Create the collation in the core database
# This is required for sorting chromosomes in the desired order
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB_CORE" <<-EOSQL
  CREATE COLLATION IF NOT EXISTS uint (
    provider = icu,
    locale = 'en-US-u-kn-true'
  );
EOSQL
