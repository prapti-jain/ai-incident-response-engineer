import os
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Incident, Metric

WINDOW_MINUTES = int(os.getenv("ANOMALY_WINDOW_MINUTES", "5"))
EXCLUDE_RECENT_SECONDS = int(os.getenv("ANOMALY_EXCLUDE_RECENT_SECONDS", "30"))
RECOVERY_SECONDS = int(os.getenv("ANOMALY_RECOVERY_SECONDS", "60"))
STD_DEV_MULTIPLIER = float(os.getenv("ANOMALY_STD_DEV_MULTIPLIER", "3"))
MIN_BASELINE_SAMPLES = int(os.getenv("ANOMALY_MIN_BASELINE_SAMPLES", "3"))
MIN_RECENT_SAMPLES = int(os.getenv("ANOMALY_MIN_RECENT_SAMPLES", "1"))
MONITORED_SERVICES = os.getenv("ANOMALY_MONITORED_SERVICES", "service-a,service-b").split(",")
MONITORED_METRICS = os.getenv("ANOMALY_MONITORED_METRICS", "error_rate,latency_ms").split(",")


@dataclass
class TrackerState:
    open_incident_id: int | None = None
    recovery_started_at: datetime | None = None


@dataclass
class MetricCheckResult:
    service: str
    metric_name: str
    baseline_count: int
    recent_count: int
    recent_mean: float | None
    baseline_mean: float | None
    baseline_stdev: float | None
    threshold: float | None
    anomalous: bool
    skip_reason: str | None = None
    action: str | None = None


_trackers: dict[tuple[str, str], TrackerState] = {}


def _get_tracker(service: str, metric_name: str) -> TrackerState:
    key = (service, metric_name)
    if key not in _trackers:
        _trackers[key] = TrackerState()
    return _trackers[key]


def evaluate_metric(
    baseline_values: list[float],
    recent_values: list[float],
) -> tuple[bool, float | None, float | None, float | None, str | None]:
    if len(recent_values) < MIN_RECENT_SAMPLES:
        return False, None, None, None, f"no recent samples in last {EXCLUDE_RECENT_SECONDS}s window"

    recent_mean = statistics.mean(recent_values)

    if len(baseline_values) < MIN_BASELINE_SAMPLES:
        return (
            False,
            None,
            None,
            None,
            f"insufficient baseline ({len(baseline_values)} samples, need {MIN_BASELINE_SAMPLES}) "
            f"— normal traffic must be older than {EXCLUDE_RECENT_SECONDS}s",
        )

    mean = statistics.mean(baseline_values)
    stdev = statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0.0
    threshold = mean + STD_DEV_MULTIPLIER * stdev

    if stdev == 0:
        anomalous = recent_mean > mean
    else:
        anomalous = recent_mean > threshold

    return anomalous, mean, stdev, threshold, None


def _fetch_windows(
    db: Session,
    *,
    service: str,
    metric_name: str,
    now: datetime,
) -> tuple[list[float], list[float]]:
    window_start = now - timedelta(minutes=WINDOW_MINUTES)
    baseline_end = now - timedelta(seconds=EXCLUDE_RECENT_SECONDS)

    baseline_values = list(
        db.scalars(
            select(Metric.value).where(
                Metric.service == service,
                Metric.metric_name == metric_name,
                Metric.timestamp >= window_start,
                Metric.timestamp < baseline_end,
            )
        ).all()
    )

    recent_values = list(
        db.scalars(
            select(Metric.value).where(
                Metric.service == service,
                Metric.metric_name == metric_name,
                Metric.timestamp >= baseline_end,
                Metric.timestamp <= now,
            )
        ).all()
    )

    return baseline_values, recent_values


def _open_incident(
    db: Session,
    *,
    service: str,
    metric_name: str,
    now: datetime,
) -> Incident:
    trigger_type = f"{service}:{metric_name}"
    incident = Incident(
        started_at=now,
        ended_at=None,
        trigger_type=trigger_type,
        status="open",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def _resolve_incident(db: Session, incident_id: int, now: datetime) -> None:
    incident = db.get(Incident, incident_id)
    if incident is None or incident.status != "open":
        return
    incident.ended_at = now
    incident.status = "resolved"
    db.commit()


def sync_trackers_from_db(db: Session) -> None:
    open_incidents = db.scalars(
        select(Incident).where(Incident.status == "open").order_by(Incident.started_at)
    ).all()

    for incident in open_incidents:
        if ":" not in incident.trigger_type:
            continue
        service, metric_name = incident.trigger_type.split(":", 1)
        tracker = _get_tracker(service, metric_name)
        tracker.open_incident_id = incident.id
        tracker.recovery_started_at = None


def format_check_log(result: MetricCheckResult) -> str:
    parts = [
        f"anomaly check: service={result.service} metric={result.metric_name}",
        f"baseline_n={result.baseline_count} recent_n={result.recent_count}",
    ]
    if result.recent_mean is not None:
        parts.append(f"recent_mean={result.recent_mean:.2f}")
    if result.baseline_mean is not None:
        parts.append(f"mean={result.baseline_mean:.2f}")
    if result.baseline_stdev is not None:
        parts.append(f"stddev={result.baseline_stdev:.2f}")
    if result.threshold is not None:
        parts.append(f"threshold={result.threshold:.2f}")
    parts.append(f"anomalous={result.anomalous}")
    if result.skip_reason:
        parts.append(f"skip={result.skip_reason}")
    if result.action:
        parts.append(f"action={result.action}")
    return " ".join(parts)


def run_detection_cycle(db: Session) -> list[MetricCheckResult]:
    now = datetime.now(timezone.utc)
    results: list[MetricCheckResult] = []

    for service in MONITORED_SERVICES:
        service = service.strip()
        if not service:
            continue

        for metric_name in MONITORED_METRICS:
            metric_name = metric_name.strip()
            if not metric_name:
                continue

            baseline, recent = _fetch_windows(
                db, service=service, metric_name=metric_name, now=now
            )

            anomalous, mean, stdev, threshold, skip_reason = evaluate_metric(
                baseline, recent
            )
            recent_mean = statistics.mean(recent) if recent else None

            result = MetricCheckResult(
                service=service,
                metric_name=metric_name,
                baseline_count=len(baseline),
                recent_count=len(recent),
                recent_mean=recent_mean,
                baseline_mean=mean,
                baseline_stdev=stdev,
                threshold=threshold,
                anomalous=anomalous,
                skip_reason=skip_reason,
            )

            tracker = _get_tracker(service, metric_name)

            if anomalous:
                tracker.recovery_started_at = None
                if tracker.open_incident_id is None:
                    incident = _open_incident(
                        db, service=service, metric_name=metric_name, now=now
                    )
                    tracker.open_incident_id = incident.id
                    result.action = f"opened incident {incident.id}"
                else:
                    result.action = f"incident {tracker.open_incident_id} still open"
            elif tracker.open_incident_id is not None:
                if tracker.recovery_started_at is None:
                    tracker.recovery_started_at = now
                    result.action = "recovery timer started"
                elif (now - tracker.recovery_started_at).total_seconds() >= RECOVERY_SECONDS:
                    incident_id = tracker.open_incident_id
                    _resolve_incident(db, incident_id, now)
                    result.action = f"resolved incident {incident_id}"
                    tracker.open_incident_id = None
                    tracker.recovery_started_at = None
                else:
                    elapsed = int((now - tracker.recovery_started_at).total_seconds())
                    result.action = f"recovering ({elapsed}s / {RECOVERY_SECONDS}s)"

            results.append(result)

    return results
