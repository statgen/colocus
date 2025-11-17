#!/bin/bash
set -euxo pipefail

docker compose exec db bash -c 'psql -U colocus -c "DROP DATABASE core WITH (FORCE)"'
docker compose exec db bash /docker-entrypoint-initdb.d/init-db.sh
docker compose exec django bash -c 'source .venv/bin/activate && python3 manage.py migrate --database=core'
docker compose exec django bash -c "
  source .venv/bin/activate
  for subdir in \$(find /data -mindepth 1 -maxdepth 1 -type d); do
    subdir=\"\${subdir%/}\"
    if [ -d \"\$subdir\" ]; then
      uv run python3 scripts/load_dataset.py \"\${subdir}\"
    fi
  done
"
