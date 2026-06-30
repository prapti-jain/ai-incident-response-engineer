#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

DATABASE_URL="${DATABASE_URL:-postgresql://telemetry:telemetry@127.0.0.1:5432/telemetry}"

bootstrap_local_postgres() {
  if ! command -v psql >/dev/null 2>&1; then
    echo "psql not found — install Postgres or Docker"
    return 1
  fi

  if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    echo "Postgres is not accepting connections on 127.0.0.1:5432"
    return 1
  fi

  echo "Bootstrapping local Postgres role/database for telemetry..."

  psql -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'telemetry') THEN
    CREATE ROLE telemetry WITH LOGIN PASSWORD 'telemetry';
  END IF;
END
$$;
SQL

  if ! psql -h 127.0.0.1 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'telemetry'" | grep -q 1; then
    psql -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE telemetry OWNER telemetry;"
  fi

  psql -h 127.0.0.1 -d telemetry -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL ON SCHEMA public TO telemetry;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO telemetry;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO telemetry;
SQL

  echo "Local Postgres ready (telemetry/telemetry @ localhost:5432/telemetry)"
}

start_docker_postgres() {
  echo "Starting Postgres via Docker..."
  docker compose -f "$ROOT/docker-compose.yml" up -d postgres

  for _ in {1..30}; do
    if docker compose -f "$ROOT/docker-compose.yml" exec -T postgres pg_isready -U telemetry -d telemetry >/dev/null 2>&1; then
      echo "Docker Postgres is ready"
      return 0
    fi
    sleep 1
  done

  echo "Docker Postgres failed to become ready"
  return 1
}

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  start_docker_postgres
else
  echo "Docker unavailable — using local Postgres"
  bootstrap_local_postgres
fi
