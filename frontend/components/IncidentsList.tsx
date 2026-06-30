"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import AppNav from "@/components/AppNav";
import IncidentStatusBadge from "@/components/IncidentStatusBadge";
import { fetchIncidents } from "@/lib/api";
import { formatDuration, formatTimestamp } from "@/lib/format";
import type { Incident } from "@/lib/types";

const POLL_MS = 5000;

export default function IncidentsList() {
  const router = useRouter();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const poll = useCallback(async () => {
    try {
      const data = await fetchIncidents();
      setIncidents(data);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incidents");
    }
  }, []);

  useEffect(() => {
    poll();
    const timer = setInterval(poll, POLL_MS);
    return () => clearInterval(timer);
  }, [poll]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4 lg:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#2a2f38] pb-4">
        <div>
          <h1 className="text-lg font-medium tracking-tight text-[#e5e7eb]">
            Incidents
          </h1>
          <p className="mt-0.5 text-xs text-[#6b7280]">
            Anomaly-detected incidents from telemetry
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <AppNav current="incidents" />
          {lastUpdated && (
            <span className="text-xs text-[#6b7280]">
              updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </header>

      {error && (
        <div className="rounded border border-[#2a2f38] px-3 py-2 text-xs text-[#f87171]">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-[#2a2f38] bg-[#12161c]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-[#2a2f38] text-xs uppercase tracking-widest text-[#6b7280]">
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Trigger</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Started</th>
                <th className="px-4 py-3 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody>
              {incidents.length === 0 && !error ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-[#6b7280]"
                  >
                    No incidents recorded yet
                  </td>
                </tr>
              ) : (
                incidents.map((incident) => (
                  <tr
                    key={incident.id}
                    role="link"
                    tabIndex={0}
                    onClick={() => router.push(`/incidents/${incident.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        router.push(`/incidents/${incident.id}`);
                      }
                    }}
                    className="cursor-pointer border-b border-[#1a1f27] last:border-b-0 hover:bg-[#0d1117] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#9ca3af]"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/incidents/${incident.id}`}
                        className="font-mono text-[#e5e7eb] hover:underline"
                        onClick={(event) => event.stopPropagation()}
                      >
                        #{incident.id}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[#9ca3af]">
                      {incident.trigger_type}
                    </td>
                    <td className="px-4 py-3">
                      <IncidentStatusBadge status={incident.status} />
                    </td>
                    <td className="px-4 py-3 text-xs text-[#9ca3af]">
                      {formatTimestamp(incident.started_at)}
                    </td>
                    <td className="px-4 py-3 text-xs text-[#9ca3af]">
                      {formatDuration(incident.started_at, incident.ended_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
