#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT/.run"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

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

usage() {
  echo "Usage: $0 [service-a|service-b|telemetry] ..."
  echo "  No args: start all services"
  echo "  One or more names: stop only those services"
}

stop_service() {
  local name="$1"
  local port="$2"
  local pid_file="$PID_DIR/$name.pid"
  local stopped=false

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
      echo "Stopped $name (pid $pid)"
      stopped=true
    else
      echo "$name: pid $pid not running"
    fi
    rm -f "$pid_file"
  fi

  if lsof -i ":$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    local orphan_pid orphan_cmd
    orphan_pid="$(lsof -i ":$port" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)"
    if [[ -n "$orphan_pid" ]]; then
      orphan_cmd="$(ps -p "$orphan_pid" -o command= 2>/dev/null || true)"
      if [[ "$orphan_cmd" == *"uvicorn main:app"* && "$orphan_cmd" == *"--port $port"* ]]; then
        kill "$orphan_pid" 2>/dev/null || kill -9 "$orphan_pid" 2>/dev/null || true
        echo "Stopped orphaned $name (pid $orphan_pid, no pid file)"
        stopped=true
      elif [[ "$stopped" == "false" ]]; then
        echo "WARNING: $name port $port in use by unrelated process (pid $orphan_pid)" >&2
        echo "  command: ${orphan_cmd:-unknown}" >&2
      fi
    fi
  fi

  if [[ "$stopped" == "false" && ! -f "$pid_file" ]]; then
    echo "$name: not running (no pid file)"
  fi
}

stop_one() {
  stop_service "$1" "$(port_for "$1")"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  for svc in "$@"; do
    stop_one "$svc"
  done
else
  stop_one telemetry
  stop_one service-b
  stop_one service-a
fi
