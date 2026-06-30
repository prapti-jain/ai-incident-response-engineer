"use client";

import { useCallback, useEffect, useState } from "react";

import InjectPanel from "@/components/InjectPanel";
import LogStream from "@/components/LogStream";
import MetricsCharts from "@/components/MetricsCharts";
import AppNav from "@/components/AppNav";
import {
  checkHealth,
  fetchRecentLogs,
  fetchRecentMetrics,
} from "@/lib/api";
import { metricsToChartPoints } from "@/lib/chart-utils";
import type { ChartPoint, RecentLog } from "@/lib/types";

const METRICS_POLL_MS = 3000;
const LOGS_POLL_MS = 2000;
const HEALTH_POLL_MS = 10000;

type ServiceHealth = {
  telemetry: boolean;
  serviceA: boolean;
  serviceB: boolean;
};

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-[#9ca3af]">
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${ok ? "bg-[#4ade80]" : "bg-[#f87171]"}`}
        aria-hidden
      />
      {label}
    </span>
  );
}

export default function Dashboard() {
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [logs, setLogs] = useState<RecentLog[]>([]);
  const [metricsUpdated, setMetricsUpdated] = useState<Date | null>(null);
  const [logsUpdated, setLogsUpdated] = useState<Date | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [health, setHealth] = useState<ServiceHealth>({
    telemetry: false,
    serviceA: false,
    serviceB: false,
  });
  const [toast, setToast] = useState<string | null>(null);

  const pollMetrics = useCallback(async () => {
    try {
      const data = await fetchRecentMetrics(15);
      setChartData(metricsToChartPoints(data.items));
      setMetricsUpdated(new Date());
      setMetricsError(null);
    } catch (err) {
      setMetricsError(
        err instanceof Error ? err.message : "Failed to load metrics",
      );
    }
  }, []);

  const pollLogs = useCallback(async () => {
    try {
      const data = await fetchRecentLogs(100);
      setLogs(data.items);
      setLogsUpdated(new Date());
      setLogsError(null);
    } catch (err) {
      setLogsError(err instanceof Error ? err.message : "Failed to load logs");
    }
  }, []);

  const pollHealth = useCallback(async () => {
    const [telemetry, serviceA, serviceB] = await Promise.all([
      checkHealth("telemetry"),
      checkHealth("service-a"),
      checkHealth("service-b"),
    ]);
    setHealth({ telemetry, serviceA, serviceB });
  }, []);

  useEffect(() => {
    pollMetrics();
    pollLogs();
    pollHealth();

    const metricsTimer = setInterval(pollMetrics, METRICS_POLL_MS);
    const logsTimer = setInterval(pollLogs, LOGS_POLL_MS);
    const healthTimer = setInterval(pollHealth, HEALTH_POLL_MS);

    return () => {
      clearInterval(metricsTimer);
      clearInterval(logsTimer);
      clearInterval(healthTimer);
    };
  }, [pollMetrics, pollLogs, pollHealth]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 lg:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#2a2f38] pb-4">
        <div>
          <h1 className="text-lg font-medium tracking-tight text-[#e5e7eb]">
            Incident Response — Live Dashboard
          </h1>
          <p className="mt-0.5 text-xs text-[#6b7280]">
            service-a gateway · service-b worker · telemetry store
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <AppNav current="dashboard" />
          <div className="flex flex-wrap gap-4">
            <StatusDot ok={health.telemetry} label="telemetry" />
            <StatusDot ok={health.serviceA} label="service-a" />
            <StatusDot ok={health.serviceB} label="service-b" />
          </div>
        </div>
      </header>

      {toast && (
        <div className="rounded border border-[#2a2f38] bg-[#12161c] px-3 py-2 text-xs text-[#9ca3af]">
          {toast}
        </div>
      )}

      {metricsError && (
        <div className="rounded border border-[#2a2f38] px-3 py-2 text-xs text-[#f87171]">
          metrics: {metricsError}
        </div>
      )}

      <InjectPanel onInjected={setToast} />

      <MetricsCharts data={chartData} lastUpdated={metricsUpdated} />

      <LogStream logs={logs} lastUpdated={logsUpdated} error={logsError} />
    </div>
  );
}
