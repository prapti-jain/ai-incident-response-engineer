from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LogIngest(BaseModel):
    service: str = Field(max_length=64)
    timestamp: datetime
    level: str = Field(max_length=16)
    message: str
    trace_id: str = Field(max_length=64)


class MetricIngest(BaseModel):
    service: str = Field(max_length=64)
    timestamp: datetime
    metric_name: str = Field(max_length=64)
    value: float


class IngestResponse(BaseModel):
    id: int


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    ended_at: datetime | None
    trigger_type: str
    status: str
    rca_report: dict | None
    postmortem: dict | None


class EvidenceItemOut(BaseModel):
    id: int
    source: Literal["logs", "metrics"]
    service: str
    timestamp: datetime
    level: str | None = None
    message: str | None = None
    trace_id: str | None = None
    metric_name: str | None = None
    value: float | None = None


class EvidenceResponse(BaseModel):
    incident_id: int
    trigger_type: str
    incident_started_at: datetime
    incident_ended_at: datetime | None
    window_start: datetime
    window_end: datetime
    total_items: int
    returned_items: int
    omitted_items: int
    sampled: bool
    items: list[EvidenceItemOut]


class RootCauseOut(BaseModel):
    rank: int
    summary: str
    evidence_ids: list[int]
    justification: str
    evidence: list[EvidenceItemOut]


class AnalyzeResponse(BaseModel):
    incident_id: int
    trigger_type: str
    rca_report: dict
    causes: list[RootCauseOut]
    all_cited_evidence: list[EvidenceItemOut]
    evidence_summary: dict


class TimelineEntryOut(BaseModel):
    timestamp: datetime
    description: str


class ImpactOut(BaseModel):
    description: str
    peak_error_rate: float
    peak_latency_ms: float


class PostmortemOut(BaseModel):
    summary: str
    timeline: list[TimelineEntryOut]
    root_cause: str
    impact: ImpactOut
    action_items: list[str]


class PostmortemResponse(BaseModel):
    incident_id: int
    trigger_type: str
    postmortem: PostmortemOut
    metric_peaks: dict


class RecentMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    timestamp: datetime
    metric_name: str
    value: float


class RecentMetricsResponse(BaseModel):
    window_minutes: int
    window_start: datetime
    window_end: datetime
    items: list[RecentMetricOut]


class RecentLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    timestamp: datetime
    level: str
    message: str
    trace_id: str


class RecentLogsResponse(BaseModel):
    limit: int
    items: list[RecentLogOut]
