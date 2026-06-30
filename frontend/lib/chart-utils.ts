import type { ChartPoint, RecentMetric } from "./types";

function bucketKey(iso: string): string {
  const d = new Date(iso);
  d.setMilliseconds(0);
  return d.toISOString();
}

function formatLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function metricsToChartPoints(items: RecentMetric[]): ChartPoint[] {
  const buckets = new Map<string, ChartPoint>();

  for (const item of items) {
    const key = bucketKey(item.timestamp);
    let point = buckets.get(key);
    if (!point) {
      point = {
        ts: new Date(key).getTime(),
        label: formatLabel(key),
      };
      buckets.set(key, point);
    }

    const field =
      item.service === "service-a"
        ? item.metric_name === "error_rate"
          ? "service_a_error_rate"
          : "service_a_latency_ms"
        : item.metric_name === "error_rate"
          ? "service_b_error_rate"
          : "service_b_latency_ms";

    point[field as keyof ChartPoint] = item.value as never;
  }

  return Array.from(buckets.values()).sort((a, b) => a.ts - b.ts);
}
