#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT/.run"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
mkdir -p "$PID_DIR"

FAILED=0

usage() {
  cat <<EOF
Usage: $0 [service-a|service-b|telemetry] ...

  No args:           bootstrap DB, migrate, start all services
  One or more names: force-restart only those services (dependency order)

Examples:
  $0
  $0 telemetry
  $0 telemetry service-a service-b
EOF
}

port_for() {
  case "$1" in
    telemetry) echo 8002 ;;
    service-a) echo 8000 ;;
    service-b) echo 8001 ;;
    *)
      echo "ERROR: unknown service '$1' (expected service-a, service-b, or telemetry)" >&2
      exit 1
      ;;
  esac
}

setup_service() {
  local name="$1"
  local dir="$ROOT/services/$name"

  if [[ ! -d "$dir/.venv" ]]; then
    echo "Creating venv for $name..."
    python3 -m venv "$dir/.venv"
  fi

  echo "Installing dependencies for $name..."
  if ! "$dir/.venv/bin/pip" install -q -r "$dir/requirements.txt"; then
    echo "ERROR: pip install failed for $name" >&2
    return 1
  fi
}

prepare_database() {
  "$ROOT/scripts/bootstrap-db.sh"
  setup_service telemetry || return 1
  echo "Running Alembic migrations..."
  if ! (cd "$ROOT/services/telemetry" && .venv/bin/alembic upgrade head); then
    echo "ERROR: Alembic migrations failed" >&2
    return 1
  fi
}

stop_service() {
  "$ROOT/scripts/stop.sh" "$1"
}

start_service() {
  local name="$1"
  local port="$2"
  local force_restart="${3:-false}"
  local pid_file="$PID_DIR/$name.pid"
  local log_file="$PID_DIR/$name.log"
  local service_dir="$ROOT/services/$name"

  if [[ "$force_restart" == "true" ]]; then
    stop_service "$name"
    sleep 0.5
  elif [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (pid $(cat "$pid_file")) on port $port — skipping"
    echo "  To pick up code changes: ./scripts/start.sh $name"
    return 0
  fi

  rm -f "$pid_file"

  if lsof -i ":$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    local orphan_pid orphan_cmd
    orphan_pid="$(lsof -i ":$port" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)"
    orphan_cmd=""
    if [[ -n "$orphan_pid" ]]; then
      orphan_cmd="$(ps -p "$orphan_pid" -o command= 2>/dev/null || true)"
    fi

    if [[ "$orphan_cmd" == *"$service_dir"* ]] || [[ "$orphan_cmd" == *"uvicorn main:app"* && "$orphan_cmd" == *"--port $port"* ]]; then
      echo "$name: stopping orphaned process on port $port (pid $orphan_pid)"
      kill "$orphan_pid" 2>/dev/null || kill -9 "$orphan_pid" 2>/dev/null || true
      sleep 0.5
    else
      echo "ERROR: $name port $port already in use (pid ${orphan_pid:-unknown})" >&2
      echo "  command: ${orphan_cmd:-unknown}" >&2
      return 1
    fi
  fi

  echo "Starting $name on port $port..."
  cd "$service_dir"
  nohup .venv/bin/uvicorn main:app --host 127.0.0.1 --port "$port" >>"$log_file" 2>&1 &
  pid=$!
  disown "$pid" 2>/dev/null || true
  echo "$pid" >"$pid_file"
  cd "$ROOT"

  local attempt
  for attempt in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      echo "$name is up at http://127.0.0.1:$port"
      return 0
    fi
    sleep 0.25
  done

  echo "ERROR: $name failed health check on port $port after 7.5s" >&2
  echo "  See log: $log_file" >&2
  tail -20 "$log_file" >&2 || true
  return 1
}

start_one() {
  local svc="$1"
  local force="${2:-true}"

  case "$svc" in
    telemetry)
      setup_service telemetry || return 1
      start_service telemetry 8002 "$force" || return 1
      ;;
    service-b)
      setup_service service-b || return 1
      start_service service-b 8001 "$force" || return 1
      ;;
    service-a)
      setup_service service-a || return 1
      start_service service-a 8000 "$force" || return 1
      ;;
    *)
      echo "ERROR: unknown service '$svc'" >&2
      return 1
      ;;
  esac
}

order_services() {
  local want svc
  for want in telemetry service-b service-a; do
    for svc in "$@"; do
      if [[ "$svc" == "$want" ]]; then
        echo "$svc"
      fi
    done
  done
}

verify_services() {
  local svc port ok=0
  echo
  echo "=== health checks ==="
  for svc in "$@"; do
    port="$(port_for "$svc")"
    if curl -sf "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      echo "OK  $svc http://127.0.0.1:$port/health"
      curl -sf "http://127.0.0.1:$port/health"
      echo
    else
      echo "FAIL $svc http://127.0.0.1:$port/health" >&2
      ok=1
    fi
  done
  return "$ok"
}

start_requested() {
  local -a requested=()
  local svc needs_db=false

  while IFS= read -r svc; do
    [[ -n "$svc" ]] && requested+=("$svc")
  done < <(order_services "$@")

  if [[ ${#requested[@]} -eq 0 ]]; then
    echo "ERROR: no valid services in: $*" >&2
    exit 1
  fi

  for svc in "${requested[@]}"; do
    [[ "$svc" == "telemetry" ]] && needs_db=true
  done

  if $needs_db; then
    prepare_database || exit 1
  fi

  for svc in "${requested[@]}"; do
    if ! start_one "$svc" true; then
      FAILED=1
      echo "ERROR: failed to start $svc" >&2
    fi
  done

  if ! verify_services "${requested[@]}"; then
    FAILED=1
  fi

  if [[ "$FAILED" -ne 0 ]]; then
    echo "ERROR: one or more services failed to start" >&2
    exit 1
  fi
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  start_requested "$@"
  exit 0
fi

prepare_database || exit 1
setup_service service-b || exit 1
setup_service service-a || exit 1

for svc in telemetry service-b service-a; do
  if ! start_one "$svc" false; then
    FAILED=1
    echo "ERROR: failed to start $svc" >&2
  fi
done

if ! verify_services telemetry service-b service-a; then
  FAILED=1
fi

if [[ "$FAILED" -ne 0 ]]; then
  echo "ERROR: one or more services failed to start" >&2
  exit 1
fi

echo
echo "Ready."
echo "  Gateway:   curl -X POST http://127.0.0.1:8000/request"
echo "  Telemetry: curl http://127.0.0.1:8002/health"
echo "  Incidents: curl http://127.0.0.1:8002/incidents"
echo "  Restart:   ./scripts/start.sh telemetry service-a service-b"
