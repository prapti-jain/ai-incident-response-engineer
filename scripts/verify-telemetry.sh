#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
PGPASSWORD="${PGPASSWORD:-telemetry}"

echo "=== telemetry health ==="
curl -sf http://127.0.0.1:8002/health | python3 -m json.tool || echo "telemetry not reachable on :8002"

echo
echo "=== row counts ==="
psql -h 127.0.0.1 -U telemetry -d telemetry -c "SELECT 'logs' AS table, COUNT(*) FROM logs UNION ALL SELECT 'metrics', COUNT(*) FROM metrics UNION ALL SELECT 'incidents', COUNT(*) FROM incidents;"

echo
echo "=== recent logs ==="
psql -h 127.0.0.1 -U telemetry -d telemetry -c "SELECT id, service, level, left(message, 50) AS message, trace_id FROM logs ORDER BY id DESC LIMIT 10;"

echo
echo "=== recent metrics ==="
psql -h 127.0.0.1 -U telemetry -d telemetry -c "SELECT id, service, metric_name, round(value::numeric, 2) AS value FROM metrics ORDER BY id DESC LIMIT 10;"

echo
echo "=== incidents ==="
psql -h 127.0.0.1 -U telemetry -d telemetry -c "SELECT id, trigger_type, status, started_at, ended_at FROM incidents ORDER BY id DESC LIMIT 10;"
