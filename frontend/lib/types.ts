export type RecentMetric = {
  id: number;
  service: string;
  timestamp: string;
  metric_name: string;
  value: number;
};

export type RecentMetricsResponse = {
  window_minutes: number;
  window_start: string;
  window_end: string;
  items: RecentMetric[];
};

export type RecentLog = {
  id: number;
  service: string;
  timestamp: string;
  level: string;
  message: string;
  trace_id: string;
};

export type RecentLogsResponse = {
  limit: number;
  items: RecentLog[];
};

export type InjectMode = "latency" | "error" | "cpu_spike" | "none";

export type InjectResult = {
  mode: InjectMode;
  magnitude: number;
};

export type ChartPoint = {
  ts: number;
  label: string;
  service_a_error_rate?: number;
  service_b_error_rate?: number;
  service_a_latency_ms?: number;
  service_b_latency_ms?: number;
};

export type Incident = {
  id: number;
  started_at: string;
  ended_at: string | null;
  trigger_type: string;
  status: string;
  rca_report: RcaReport | null;
  postmortem: PostmortemReport | null;
};

export type EvidenceItem = {
  id: number;
  source: "logs" | "metrics";
  service: string;
  timestamp: string;
  level?: string | null;
  message?: string | null;
  trace_id?: string | null;
  metric_name?: string | null;
  value?: number | null;
};

export type EvidenceResponse = {
  incident_id: number;
  trigger_type: string;
  incident_started_at: string;
  incident_ended_at: string | null;
  window_start: string;
  window_end: string;
  total_items: number;
  returned_items: number;
  omitted_items: number;
  sampled: boolean;
  items: EvidenceItem[];
};

export type RootCause = {
  rank: number;
  summary: string;
  evidence_ids: number[];
  justification: string;
};

export type RcaReport = {
  causes: RootCause[];
};

export type CauseWithEvidence = RootCause & {
  evidence: EvidenceItem[];
};

export type AnalyzeResponse = {
  incident_id: number;
  trigger_type: string;
  rca_report: RcaReport;
  causes: CauseWithEvidence[];
  all_cited_evidence: EvidenceItem[];
  evidence_summary: Record<string, unknown>;
};

export type TimelineEntry = {
  timestamp: string;
  description: string;
};

export type PostmortemReport = {
  summary: string;
  timeline: TimelineEntry[];
  root_cause: string;
  impact: {
    description: string;
    peak_error_rate: number;
    peak_latency_ms: number;
  };
  action_items: string[];
};

export type PostmortemResponse = {
  incident_id: number;
  trigger_type: string;
  postmortem: PostmortemReport;
  metric_peaks: Record<string, unknown>;
};
