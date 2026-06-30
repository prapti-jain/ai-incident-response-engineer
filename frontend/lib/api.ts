import type {
  AnalyzeResponse,
  EvidenceResponse,
  Incident,
  InjectMode,
  InjectResult,
  PostmortemResponse,
  RecentLogsResponse,
  RecentMetricsResponse,
} from "./types";

const TELEMETRY_URL =
  process.env.NEXT_PUBLIC_TELEMETRY_URL ?? "http://localhost:8002";
const SERVICE_B_URL =
  process.env.NEXT_PUBLIC_SERVICE_B_URL ?? "http://localhost:8001";
const SERVICE_A_URL =
  process.env.NEXT_PUBLIC_SERVICE_A_URL ?? "http://localhost:8000";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchRecentMetrics(
  minutes = 15,
): Promise<RecentMetricsResponse> {
  return fetchJson(
    `${TELEMETRY_URL}/metrics/recent?minutes=${minutes}`,
    { cache: "no-store" },
  );
}

export async function fetchRecentLogs(
  limit = 100,
): Promise<RecentLogsResponse> {
  return fetchJson(`${TELEMETRY_URL}/logs/recent?limit=${limit}`, {
    cache: "no-store",
  });
}

export async function injectFailure(
  mode: InjectMode,
  magnitude: number,
): Promise<InjectResult> {
  return fetchJson(`${SERVICE_B_URL}/admin/inject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, magnitude }),
  });
}

export async function checkHealth(
  service: "telemetry" | "service-a" | "service-b",
): Promise<boolean> {
  const base =
    service === "telemetry"
      ? TELEMETRY_URL
      : service === "service-a"
        ? SERVICE_A_URL
        : SERVICE_B_URL;
  try {
    const response = await fetch(`${base}/health`, { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

export async function fetchIncidents(): Promise<Incident[]> {
  return fetchJson(`${TELEMETRY_URL}/incidents`, { cache: "no-store" });
}

export async function fetchIncident(id: number): Promise<Incident> {
  return fetchJson(`${TELEMETRY_URL}/incidents/${id}`, { cache: "no-store" });
}

export async function fetchIncidentEvidence(
  id: number,
): Promise<EvidenceResponse> {
  return fetchJson(`${TELEMETRY_URL}/incidents/${id}/evidence`, {
    cache: "no-store",
  });
}

export async function analyzeIncident(id: number): Promise<AnalyzeResponse> {
  return fetchJson(`${TELEMETRY_URL}/incidents/${id}/analyze`, {
    method: "POST",
    cache: "no-store",
  });
}

export async function generatePostmortem(
  id: number,
): Promise<PostmortemResponse> {
  return fetchJson(`${TELEMETRY_URL}/incidents/${id}/postmortem`, {
    method: "POST",
    cache: "no-store",
  });
}

export { SERVICE_A_URL, SERVICE_B_URL, TELEMETRY_URL };
