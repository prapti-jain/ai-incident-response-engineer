from datetime import datetime, timezone
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import get_gemini_api_key, get_gemini_model
from errors import AnalyzeError, gemini_client_error_to_analyze_error
from evidence import compute_evidence_window
from models import Incident, Metric

SYSTEM_PROMPT = """You are an expert SRE writing a post-incident review.

You will receive:
- Incident metadata (start/end, trigger)
- An existing root cause analysis (RCA) report
- Evidence items (logs and metrics) from the incident window
- Computed metric peaks during the window (use these EXACT numeric values)
- Timeline-eligible events: a list of real timestamps with descriptions you MAY use

CRITICAL RULES:
1. Every timeline entry timestamp MUST be copied EXACTLY from the "Timeline-eligible events"
   section. Do NOT invent, interpolate, round, or guess timestamps.
2. Set impact.peak_error_rate and impact.peak_latency_ms to the EXACT values provided
   in "Metric peaks during incident window".
3. Base root_cause on the RCA report and evidence. Do not contradict cited evidence.
4. action_items should be concrete, actionable follow-ups for an engineering team.

Respond ONLY with JSON matching the required schema."""


class TimelineEntry(BaseModel):
    timestamp: datetime
    description: str


class Impact(BaseModel):
    description: str
    peak_error_rate: float = Field(ge=0)
    peak_latency_ms: float = Field(ge=0)


class PostmortemReport(BaseModel):
    summary: str
    timeline: list[TimelineEntry] = Field(min_length=1)
    root_cause: str
    impact: Impact
    action_items: list[str] = Field(min_length=1)

    @field_validator("timeline")
    @classmethod
    def timeline_must_be_chronological(
        cls, timeline: list[TimelineEntry]
    ) -> list[TimelineEntry]:
        timestamps = [entry.timestamp for entry in timeline]
        if timestamps != sorted(timestamps):
            raise ValueError("timeline entries must be in chronological order")
        return timeline


def _normalize_ts(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _ts_key(ts: datetime) -> str:
    return _normalize_ts(ts).isoformat()


def fetch_metric_peaks(
    db: Session,
    *,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    rows = db.execute(
        select(
            Metric.service,
            Metric.metric_name,
            func.max(Metric.value).label("peak_value"),
        )
        .where(
            Metric.timestamp >= window_start,
            Metric.timestamp <= window_end,
            Metric.metric_name.in_(("error_rate", "latency_ms")),
        )
        .group_by(Metric.service, Metric.metric_name)
    ).all()

    by_service: dict[str, dict[str, float]] = {}
    peak_error_rate = 0.0
    peak_latency_ms = 0.0

    for service, metric_name, peak_value in rows:
        by_service.setdefault(service, {})[metric_name] = float(peak_value)
        if metric_name == "error_rate":
            peak_error_rate = max(peak_error_rate, float(peak_value))
        elif metric_name == "latency_ms":
            peak_latency_ms = max(peak_latency_ms, float(peak_value))

    peak_error_rows = db.scalars(
        select(Metric)
        .where(
            Metric.timestamp >= window_start,
            Metric.timestamp <= window_end,
            Metric.metric_name == "error_rate",
            Metric.value == peak_error_rate,
        )
        .order_by(Metric.timestamp)
        .limit(1)
    ).first()

    peak_latency_rows = db.scalars(
        select(Metric)
        .where(
            Metric.timestamp >= window_start,
            Metric.timestamp <= window_end,
            Metric.metric_name == "latency_ms",
            Metric.value == peak_latency_ms,
        )
        .order_by(Metric.timestamp)
        .limit(1)
    ).first()

    return {
        "peak_error_rate": peak_error_rate,
        "peak_latency_ms": peak_latency_ms,
        "by_service": by_service,
        "peak_error_rate_at": (
            _normalize_ts(peak_error_rows.timestamp) if peak_error_rows else None
        ),
        "peak_latency_ms_at": (
            _normalize_ts(peak_latency_rows.timestamp) if peak_latency_rows else None
        ),
    }


def _select_timeline_candidates(
    evidence_index: dict[int, dict],
    peaks: dict[str, Any],
    incident: Incident,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_ts: set[str] = set()

    def add(ts: datetime, description: str, *, evidence_id: int | None = None) -> None:
        key = _ts_key(ts)
        if key in seen_ts:
            return
        seen_ts.add(key)
        candidates.append(
            {
                "timestamp": _normalize_ts(ts),
                "description_hint": description,
                "evidence_id": evidence_id,
            }
        )

    started = _normalize_ts(incident.started_at)
    add(started, f"Incident opened ({incident.trigger_type})")

    if incident.ended_at is not None:
        add(
            _normalize_ts(incident.ended_at),
            f"Incident resolved ({incident.trigger_type})",
        )

    for item in evidence_index.values():
        if item["source"] == "logs" and item.get("level") == "error":
            add(
                item["timestamp"],
                f"{item['service']}: {item['message']}",
                evidence_id=item["id"],
            )

    for item in evidence_index.values():
        if item["source"] != "metrics":
            continue
        ts = item["timestamp"]
        if item["metric_name"] == "error_rate" and item["value"] == peaks["peak_error_rate"]:
            add(
                ts,
                f"{item['service']} error_rate peaked at {item['value']}%",
                evidence_id=item["id"],
            )
        if item["metric_name"] == "latency_ms" and item["value"] == peaks["peak_latency_ms"]:
            add(
                ts,
                f"{item['service']} latency_ms peaked at {item['value']}ms",
                evidence_id=item["id"],
            )

    candidates.sort(key=lambda c: c["timestamp"])
    return candidates


def _format_rca(rca_report: dict[str, Any]) -> str:
    lines = ["Root cause analysis:"]
    for cause in rca_report.get("causes", []):
        lines.append(
            f"  Rank {cause['rank']}: {cause['summary']} "
            f"(evidence_ids={cause.get('evidence_ids', [])})"
        )
        lines.append(f"    Justification: {cause.get('justification', '')}")
    return "\n".join(lines)


def _format_prompt(
    *,
    incident: Incident,
    evidence: dict[str, Any],
    rca_report: dict[str, Any],
    peaks: dict[str, Any],
    timeline_candidates: list[dict[str, Any]],
) -> str:
    lines = [
        f"Incident ID: {incident.id}",
        f"Trigger: {incident.trigger_type}",
        f"Status: {incident.status}",
        f"Started: {incident.started_at}",
        f"Ended: {incident.ended_at}",
        f"Evidence window: {evidence['window_start']} to {evidence['window_end']}",
        "",
        "Metric peaks during incident window (use EXACT values for impact fields):",
        f"  peak_error_rate: {peaks['peak_error_rate']}",
        f"  peak_latency_ms: {peaks['peak_latency_ms']}",
        f"  by_service: {peaks['by_service']}",
        "",
        _format_rca(rca_report),
        "",
        "Timeline-eligible events (ONLY use these timestamps for timeline entries):",
    ]
    for candidate in timeline_candidates:
        eid = candidate.get("evidence_id")
        suffix = f" [evidence_id={eid}]" if eid is not None else ""
        lines.append(
            f"  - {candidate['timestamp'].isoformat()}: "
            f"{candidate['description_hint']}{suffix}"
        )

    lines.extend(
        [
            "",
            f"Evidence items (sampled={evidence['sampled']}, "
            f"{evidence['returned_items']} of {evidence['total_items']}):",
        ]
    )
    for item in evidence["items"]:
        if item["source"] == "logs":
            detail = (
                f"level={item['level']} message={item['message']!r} "
                f"trace_id={item.get('trace_id')}"
            )
        else:
            detail = f"metric={item['metric_name']} value={item['value']}"
        lines.append(
            f"  [{item['id']}] {item['timestamp']} {item['service']} "
            f"{item['source']} {detail}"
        )
    return "\n".join(lines)


def _call_gemini(prompt: str, validation_error: str | None = None) -> str:
    api_key = get_gemini_api_key()
    if not api_key:
        raise AnalyzeError(
            message=(
                "GEMINI_API_KEY is not set. Add it to services/telemetry/.env "
                "or export it in the environment before calling /postmortem."
            ),
            status_code=503,
            error_type="missing_api_key",
        )

    model = get_gemini_model()
    client = genai.Client(api_key=api_key)
    user_prompt = prompt
    if validation_error:
        user_prompt += (
            "\n\nYour previous response failed validation. Fix it.\n"
            f"Validation error: {validation_error}\n"
            "Return valid JSON only."
        )

    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=PostmortemReport,
                temperature=0.2,
            ),
        )
    except genai_errors.ClientError as exc:
        raise gemini_client_error_to_analyze_error(exc) from exc
    except Exception as exc:
        raise AnalyzeError(
            message=f"Unexpected Gemini SDK error: {exc}",
            status_code=502,
            error_type="gemini_sdk_error",
        ) from exc

    text = response.text
    if not text:
        raise AnalyzeError(
            message="Gemini returned an empty response",
            status_code=502,
            error_type="empty_gemini_response",
        )
    return text


def _validate_timeline_timestamps(
    report: PostmortemReport,
    allowed_timestamps: set[str],
) -> None:
    invalid = []
    for entry in report.timeline:
        key = _ts_key(entry.timestamp)
        if key not in allowed_timestamps:
            invalid.append(key)
    if invalid:
        raise ValueError(
            f"timeline contains timestamps not present in evidence: {invalid}. "
            f"Allowed timestamps: {sorted(allowed_timestamps)}"
        )


def _validate_impact_peaks(report: PostmortemReport, peaks: dict[str, Any]) -> None:
    eps = 0.01
    if abs(report.impact.peak_error_rate - peaks["peak_error_rate"]) > eps:
        raise ValueError(
            f"impact.peak_error_rate must be {peaks['peak_error_rate']}, "
            f"got {report.impact.peak_error_rate}"
        )
    if abs(report.impact.peak_latency_ms - peaks["peak_latency_ms"]) > eps:
        raise ValueError(
            f"impact.peak_latency_ms must be {peaks['peak_latency_ms']}, "
            f"got {report.impact.peak_latency_ms}"
        )


def generate_postmortem(
    db: Session,
    incident: Incident,
    evidence: dict[str, Any],
    evidence_index: dict[int, dict],
    rca_report: dict[str, Any],
) -> PostmortemReport:
    window_start, window_end = compute_evidence_window(incident)
    peaks = fetch_metric_peaks(db, window_start=window_start, window_end=window_end)
    timeline_candidates = _select_timeline_candidates(evidence_index, peaks, incident)
    allowed_timestamps = {_ts_key(c["timestamp"]) for c in timeline_candidates}

    prompt = _format_prompt(
        incident=incident,
        evidence=evidence,
        rca_report=rca_report,
        peaks=peaks,
        timeline_candidates=timeline_candidates,
    )

    last_error: str | None = None
    for attempt in range(2):
        raw = _call_gemini(prompt, validation_error=last_error)
        try:
            report = PostmortemReport.model_validate_json(raw)
            _validate_timeline_timestamps(report, allowed_timestamps)
            _validate_impact_peaks(report, peaks)
            return report
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            if attempt == 1:
                raise AnalyzeError(
                    message=f"Gemini postmortem response failed validation: {last_error}",
                    status_code=502,
                    error_type="postmortem_validation_error",
                ) from exc

    raise AnalyzeError(
        message="Gemini postmortem generation failed",
        status_code=502,
        error_type="postmortem_generation_failed",
    )
