#!/bin/bash
set -euxo pipefail

# This is to avoid conflict with how containers get named in the other compose stack
export COMPOSE_PROJECT_NAME="colocus_tests"

# Ensure cleanup on exit
trap 'docker compose -f docker-compose.tests.yml down --volumes --remove-orphans' EXIT

# Run the test suite
docker compose -f docker-compose.tests.yml up --force-recreate --build --abort-on-container-exit --exit-code-from django

# If you want to debug into the django container:
# docker compose -f docker-compose.tests.yml run --entrypoint bash --rm django -l
