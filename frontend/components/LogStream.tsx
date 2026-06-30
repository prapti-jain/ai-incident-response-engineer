"use client";

import { useEffect, useRef } from "react";

import type { RecentLog } from "@/lib/types";

type Props = {
  logs: RecentLog[];
  lastUpdated: Date | null;
  error: string | null;
};

function levelClass(level: string): string {
  switch (level.toLowerCase()) {
    case "error":
      return "text-[#f87171]";
    case "warn":
    case "warning":
      return "text-[#fbbf24]";
    default:
      return "text-[#9ca3af]";
  }
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  });
}

export default function LogStream({ logs, lastUpdated, error }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pinnedToTop = useRef(true);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !pinnedToTop.current) return;
    el.scrollTop = 0;
  }, [logs]);

  function handleScroll() {
    const el = containerRef.current;
    if (!el) return;
    pinnedToTop.current = el.scrollTop < 24;
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-[#2a2f38] bg-[#0d1117]">
      <div className="flex items-center justify-between border-b border-[#2a2f38] px-4 py-2">
        <h2 className="text-xs uppercase tracking-widest text-[#6b7280]">
          Log stream
        </h2>
        {lastUpdated && (
          <span className="text-xs text-[#6b7280]">
            updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {error && (
        <div className="border-b border-[#2a2f38] px-4 py-2 text-xs text-[#f87171]">
          {error}
        </div>
      )}

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-2 font-mono text-[11px] leading-5"
      >
        {logs.length === 0 ? (
          <p className="px-1 py-4 text-[#6b7280]">Waiting for log entries…</p>
        ) : (
          logs.map((log) => (
            <div
              key={log.id}
              className="grid grid-cols-[auto_auto_auto_1fr] gap-x-2 border-b border-[#1a1f27] px-1 py-0.5 last:border-b-0"
            >
              <span className="text-[#6b7280]">{formatTime(log.timestamp)}</span>
              <span className="text-[#6b7280]">{log.service}</span>
              <span className={`uppercase ${levelClass(log.level)}`}>
                {log.level.padEnd(5)}
              </span>
              <span className="truncate text-[#c9d1d9]" title={log.message}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
