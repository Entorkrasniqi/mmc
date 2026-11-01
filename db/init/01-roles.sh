#!/bin/bash
# Runs once, when the PostgreSQL container initialises an empty data directory (see docker-compose.yml).
# Creates the four roles from db/roles.sql with passwords taken from the environment, then locks the application
# database down with db/database.sql (the migrator owns it; only the four roles may connect).
set -euo pipefail

: "${MINISAT_DB_PASSWORD_MIGRATOR:?must be set}"
: "${MINISAT_DB_PASSWORD_RUNNER:?must be set}"
: "${MINISAT_DB_PASSWORD_READER:?must be set}"
: "${MINISAT_DB_PASSWORD_INGEST:?must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v migrator_pw="$MINISAT_DB_PASSWORD_MIGRATOR" -v runner_pw="$MINISAT_DB_PASSWORD_RUNNER" \
     -v reader_pw="$MINISAT_DB_PASSWORD_READER" -v ingest_pw="$MINISAT_DB_PASSWORD_INGEST" \
     -f /opt/minisat/roles.sql

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /opt/minisat/database.sql
