import json
import os
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx

TELEMETRY_URL = os.getenv("TELEMETRY_URL", "http://127.0.0.1:8002")
TELEMETRY_ENABLED = os.getenv("TELEMETRY_ENABLED", "true").lower() in ("1", "true", "yes")
METRICS_WINDOW_SIZE = int(os.getenv("METRICS_WINDOW_SIZE", "100"))

_http_client = httpx.Client(timeout=2.0)
_error_window: deque[bool] = deque(maxlen=METRICS_WINDOW_SIZE)


def _emit_log(record: dict[str, Any]) -> None:
    if not TELEMETRY_ENABLED:
        return
    try:
        _http_client.post(
            f"{TELEMETRY_URL}/ingest/logs",
            json={
                "service": record["service"],
                "timestamp": record["timestamp"],
                "level": record["level"],
                "message": record["message"],
                "trace_id": record["trace_id"],
            },
        )
    except Exception:
        pass


def _emit_metric(service: str, metric_name: str, value: float, timestamp: str) -> None:
    if not TELEMETRY_ENABLED:
        return
    try:
        _http_client.post(
            f"{TELEMETRY_URL}/ingest/metrics",
            json={
                "service": service,
                "timestamp": timestamp,
                "metric_name": metric_name,
                "value": value,
            },
        )
    except Exception:
        pass


def log_event(
    *,
    service: str,
    trace_id: str,
    level: str,
    message: str,
    duration_ms: float | None = None,
    emit_metrics: bool = False,
    is_error: bool = False,
    **extra: Any,
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "timestamp": timestamp,
        "service": service,
        "trace_id": trace_id,
        "level": level,
        "message": message,
        "duration_ms": duration_ms,
    }
    record.update(extra)
    print(json.dumps(record), file=sys.stdout, flush=True)
    _emit_log(record)

    if emit_metrics and duration_ms is not None:
        _error_window.append(is_error)
        _emit_metric(service, "latency_ms", duration_ms, timestamp)
        error_rate = (sum(_error_window) / len(_error_window)) * 100.0
        _emit_metric(service, "error_rate", round(error_rate, 2), timestamp)
