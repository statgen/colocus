#!/bin/bash
set -euxo pipefail

docker compose exec db bash -c 'psql -U colocus -c "DROP DATABASE core WITH (FORCE)"'
docker compose exec db bash /docker-entrypoint-initdb.d/init-db.sh
docker compose exec django bash -c 'source .venv/bin/activate && python3 manage.py migrate --database=core'
docker compose exec django bash /opt/colocus/bin/entrypoint-migrate-and-load.sh
docker compose exec db bash -c 'psql -U colocus -d core -c "REFRESH MATERIALIZED VIEW core_colocresult_with_orphans"'
