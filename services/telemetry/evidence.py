import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Incident, LogEntry, Metric

EVIDENCE_MAX_ITEMS = int(os.getenv("EVIDENCE_MAX_ITEMS", "150"))
EVIDENCE_PADDING_MINUTES = int(os.getenv("EVIDENCE_PADDING_MINUTES", "2"))
MONITORED_SERVICES = ("service-a", "service-b")


@dataclass(frozen=True)
class RawEvidence:
    source: Literal["logs", "metrics"]
    service: str
    timestamp: datetime
    row_id: int
    level: str | None = None
    message: str | None = None
    trace_id: str | None = None
    metric_name: str | None = None
    value: float | None = None


def _ensure_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def compute_evidence_window(incident: Incident) -> tuple[datetime, datetime]:
    started_at = _ensure_aware(incident.started_at)
    window_start = started_at - timedelta(minutes=EVIDENCE_PADDING_MINUTES)
    default_end = started_at + timedelta(minutes=EVIDENCE_PADDING_MINUTES)

    if incident.ended_at is not None:
        window_end = max(default_end, _ensure_aware(incident.ended_at))
    else:
        window_end = default_end

    return window_start, window_end


def _sort_key(item: RawEvidence) -> tuple:
    source_order = 0 if item.source == "logs" else 1
    return (item.timestamp, source_order, item.service, item.row_id)


def _even_sample_indices(total: int, limit: int) -> list[int]:
    if total <= limit:
        return list(range(total))
    if limit == 1:
        return [0]

    indices: list[int] = []
    last = -1
    for i in range(limit):
        idx = round(i * (total - 1) / (limit - 1))
        if idx <= last:
            idx = last + 1
        if idx >= total:
            break
        indices.append(idx)
        last = idx
    return indices


def _fetch_logs(
    db: Session,
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[RawEvidence]:
    rows = db.scalars(
        select(LogEntry)
        .where(
            LogEntry.service.in_(MONITORED_SERVICES),
            LogEntry.timestamp >= window_start,
            LogEntry.timestamp <= window_end,
        )
        .order_by(LogEntry.timestamp, LogEntry.id)
    ).all()

    return [
        RawEvidence(
            source="logs",
            service=row.service,
            timestamp=_ensure_aware(row.timestamp),
            row_id=row.id,
            level=row.level,
            message=row.message,
            trace_id=row.trace_id,
        )
        for row in rows
    ]


def _fetch_metrics(
    db: Session,
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[RawEvidence]:
    rows = db.scalars(
        select(Metric)
        .where(
            Metric.service.in_(MONITORED_SERVICES),
            Metric.timestamp >= window_start,
            Metric.timestamp <= window_end,
        )
        .order_by(Metric.timestamp, Metric.id)
    ).all()

    return [
        RawEvidence(
            source="metrics",
            service=row.service,
            timestamp=_ensure_aware(row.timestamp),
            row_id=row.id,
            metric_name=row.metric_name,
            value=row.value,
        )
        for row in rows
    ]


def _collect_all_items(
    db: Session,
    incident: Incident,
) -> tuple[datetime, datetime, list[dict]]:
    window_start, window_end = compute_evidence_window(incident)

    raw_items = _fetch_logs(db, window_start=window_start, window_end=window_end)
    raw_items.extend(_fetch_metrics(db, window_start=window_start, window_end=window_end))
    raw_items.sort(key=_sort_key)

    all_items: list[dict] = []
    for stable_id, raw in enumerate(raw_items, start=1):
        item = {
            "id": stable_id,
            "source": raw.source,
            "service": raw.service,
            "timestamp": raw.timestamp,
        }
        if raw.source == "logs":
            item["level"] = raw.level
            item["message"] = raw.message
            item["trace_id"] = raw.trace_id
        else:
            item["metric_name"] = raw.metric_name
            item["value"] = raw.value
        all_items.append(item)

    return window_start, window_end, all_items


def build_evidence(db: Session, incident: Incident) -> dict:
    window_start, window_end, all_items = _collect_all_items(db, incident)

    total_items = len(all_items)
    sample_indices = _even_sample_indices(total_items, EVIDENCE_MAX_ITEMS)
    sampled = total_items > EVIDENCE_MAX_ITEMS
    selected = [all_items[i] for i in sample_indices]
    returned_items = len(selected)
    omitted_items = total_items - returned_items

    return {
        "incident_id": incident.id,
        "trigger_type": incident.trigger_type,
        "incident_started_at": _ensure_aware(incident.started_at),
        "incident_ended_at": (
            _ensure_aware(incident.ended_at) if incident.ended_at is not None else None
        ),
        "window_start": window_start,
        "window_end": window_end,
        "total_items": total_items,
        "returned_items": returned_items,
        "omitted_items": omitted_items,
        "sampled": sampled,
        "items": selected,
    }


def build_evidence_maps(db: Session, incident: Incident) -> tuple[dict, dict[int, dict]]:
    evidence = build_evidence(db, incident)
    _, _, all_items = _collect_all_items(db, incident)
    index = {item["id"]: item for item in all_items}
    return evidence, index
