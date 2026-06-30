import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from anomaly_detector import format_check_log, run_detection_cycle, sync_trackers_from_db
from config import get_gemini_api_key
from cors_setup import configure_cors
from database import SessionLocal, get_db
from errors import AnalyzeError, register_exception_handlers
from evidence import build_evidence, build_evidence_maps
from models import Incident, LogEntry, Metric
from postmortem import fetch_metric_peaks, generate_postmortem
from rca import analyze_incident, join_cited_evidence
from schemas import (
    AnalyzeResponse,
    EvidenceResponse,
    IncidentOut,
    IngestResponse,
    LogIngest,
    MetricIngest,
    PostmortemResponse,
    RecentLogsResponse,
    RecentMetricsResponse,
)
from evidence import compute_evidence_window, MONITORED_SERVICES

CHECK_INTERVAL_SECONDS = int(os.getenv("ANOMALY_CHECK_INTERVAL_SECONDS", "10"))
RECENT_METRICS_DEFAULT_MINUTES = int(os.getenv("RECENT_METRICS_DEFAULT_MINUTES", "15"))
RECENT_LOGS_DEFAULT_LIMIT = int(os.getenv("RECENT_LOGS_DEFAULT_LIMIT", "100"))


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
    return logging.getLogger("telemetry.anomaly")


logger = configure_logging()


async def anomaly_detection_loop(app: FastAPI) -> None:
    logger.info(
        "anomaly detection background task started (interval=%ss, first check immediate)",
        CHECK_INTERVAL_SECONDS,
    )
    while True:
        try:
            db = SessionLocal()
            try:
                results = await asyncio.to_thread(run_detection_cycle, db)
                logger.info("anomaly cycle complete: checked %d service/metric pairs", len(results))
                for result in results:
                    logger.info(format_check_log(result))
            finally:
                db.close()
        except Exception:
            logger.exception("anomaly detection cycle failed")

        app.state.anomaly_cycles = getattr(app.state, "anomaly_cycles", 0) + 1
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        sync_trackers_from_db(db)
        logger.info("synced open incident trackers from database")
    finally:
        db.close()

    app.state.anomaly_task = asyncio.create_task(anomaly_detection_loop(app))
    app.state.anomaly_cycles = 0
    logger.info("scheduled anomaly detection asyncio task")

    yield

    app.state.anomaly_task.cancel()
    try:
        await app.state.anomaly_task
    except asyncio.CancelledError:
        logger.info("anomaly detection background task cancelled")


app = FastAPI(title="telemetry", lifespan=lifespan)
register_exception_handlers(app)
configure_cors(app)


@app.get("/health")
def health(request: Request, db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    log_count = db.scalar(select(func.count()).select_from(LogEntry)) or 0
    metric_count = db.scalar(select(func.count()).select_from(Metric)) or 0
    open_incidents = (
        db.scalar(
            select(func.count()).select_from(Incident).where(Incident.status == "open")
        )
        or 0
    )
    task = getattr(request.app.state, "anomaly_task", None)
    return {
        "status": "ok",
        "service": "telemetry",
        "log_count": log_count,
        "metric_count": metric_count,
        "open_incidents": open_incidents,
        "anomaly_check_interval_seconds": CHECK_INTERVAL_SECONDS,
        "anomaly_task_running": task is not None and not task.done(),
        "anomaly_cycles_completed": getattr(request.app.state, "anomaly_cycles", 0),
        "gemini_api_key_configured": get_gemini_api_key() is not None,
    }


@app.post("/ingest/logs", response_model=IngestResponse, status_code=201)
def ingest_log(payload: LogIngest, db: Session = Depends(get_db)):
    entry = LogEntry(
        service=payload.service,
        timestamp=payload.timestamp,
        level=payload.level,
        message=payload.message,
        trace_id=payload.trace_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return IngestResponse(id=entry.id)


@app.post("/ingest/metrics", response_model=IngestResponse, status_code=201)
def ingest_metric(payload: MetricIngest, db: Session = Depends(get_db)):
    entry = Metric(
        service=payload.service,
        timestamp=payload.timestamp,
        metric_name=payload.metric_name,
        value=payload.value,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return IngestResponse(id=entry.id)


@app.get("/metrics/recent", response_model=RecentMetricsResponse)
def recent_metrics(
    minutes: int = Query(default=RECENT_METRICS_DEFAULT_MINUTES, ge=1, le=120),
    db: Session = Depends(get_db),
):
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(minutes=minutes)

    rows = db.scalars(
        select(Metric)
        .where(
            Metric.service.in_(MONITORED_SERVICES),
            Metric.metric_name.in_(("latency_ms", "error_rate")),
            Metric.timestamp >= window_start,
            Metric.timestamp <= window_end,
        )
        .order_by(Metric.timestamp, Metric.id)
    ).all()

    return {
        "window_minutes": minutes,
        "window_start": window_start,
        "window_end": window_end,
        "items": rows,
    }


@app.get("/logs/recent", response_model=RecentLogsResponse)
def recent_logs(
    limit: int = Query(default=RECENT_LOGS_DEFAULT_LIMIT, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(LogEntry)
        .where(LogEntry.service.in_(MONITORED_SERVICES))
        .order_by(LogEntry.timestamp.desc(), LogEntry.id.desc())
        .limit(limit)
    ).all()

    return {
        "limit": limit,
        "items": rows,
    }


@app.get("/incidents", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    return db.scalars(select(Incident).order_by(Incident.started_at.desc())).all()


@app.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.get("/incidents/{incident_id}/evidence", response_model=EvidenceResponse)
def get_incident_evidence(incident_id: int, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return build_evidence(db, incident)


@app.post("/incidents/{incident_id}/analyze", response_model=AnalyzeResponse)
def analyze_incident_endpoint(incident_id: int, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    evidence, evidence_index = build_evidence_maps(db, incident)

    try:
        report = analyze_incident(evidence)
    except AnalyzeError:
        raise

    joined = join_cited_evidence(report, evidence_index)
    rca_payload = report.model_dump()

    incident.rca_report = rca_payload
    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.id,
        "trigger_type": incident.trigger_type,
        "rca_report": rca_payload,
        "causes": joined["causes"],
        "all_cited_evidence": joined["all_cited_evidence"],
        "evidence_summary": {
            "total_items": evidence["total_items"],
            "returned_items": evidence["returned_items"],
            "omitted_items": evidence["omitted_items"],
            "sampled": evidence["sampled"],
            "window_start": evidence["window_start"],
            "window_end": evidence["window_end"],
        },
    }


def _ensure_rca_report(db: Session, incident: Incident) -> dict:
    if incident.rca_report is not None:
        return incident.rca_report

    evidence, _ = build_evidence_maps(db, incident)
    try:
        report = analyze_incident(evidence)
    except AnalyzeError:
        raise

    rca_payload = report.model_dump()
    incident.rca_report = rca_payload
    db.commit()
    db.refresh(incident)
    return rca_payload


@app.post("/incidents/{incident_id}/postmortem", response_model=PostmortemResponse)
def postmortem_incident_endpoint(incident_id: int, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    rca_report = _ensure_rca_report(db, incident)
    evidence, evidence_index = build_evidence_maps(db, incident)

    try:
        report = generate_postmortem(db, incident, evidence, evidence_index, rca_report)
    except AnalyzeError:
        raise

    postmortem_payload = report.model_dump(mode="json")
    incident.postmortem = postmortem_payload
    db.commit()
    db.refresh(incident)

    window_start, window_end = compute_evidence_window(incident)
    peaks = fetch_metric_peaks(db, window_start=window_start, window_end=window_end)

    return {
        "incident_id": incident.id,
        "trigger_type": incident.trigger_type,
        "postmortem": postmortem_payload,
        "metric_peaks": peaks,
    }
