"use client";

import { useState } from "react";

import { injectFailure } from "@/lib/api";
import type { InjectMode } from "@/lib/types";

const MODES: {
  mode: InjectMode;
  label: string;
  magnitude: number;
  detail: string;
}[] = [
  { mode: "latency", label: "Latency", magnitude: 500, detail: "500 ms delay" },
  { mode: "error", label: "Error", magnitude: 100, detail: "100% error rate" },
  {
    mode: "cpu_spike",
    label: "CPU spike",
    magnitude: 200,
    detail: "200 ms CPU burn",
  },
  { mode: "none", label: "Clear", magnitude: 0, detail: "Disable injection" },
];

type Props = {
  onInjected?: (message: string) => void;
};

export default function InjectPanel({ onInjected }: Props) {
  const [activeMode, setActiveMode] = useState<InjectMode | null>(null);
  const [pending, setPending] = useState<InjectMode | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleInject(mode: InjectMode, magnitude: number) {
    setPending(mode);
    setError(null);
    try {
      const result = await injectFailure(mode, magnitude);
      setActiveMode(result.mode);
      onInjected?.(
        `Injected ${result.mode}${result.magnitude ? ` (magnitude ${result.magnitude})` : ""}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Inject request failed");
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="rounded-lg border border-[#2a2f38] bg-[#12161c] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs uppercase tracking-widest text-[#6b7280]">
          Fault injection (service-b)
        </h2>
        {activeMode && (
          <span className="text-xs text-[#9ca3af]">
            active:{" "}
            <span
              className={
                activeMode === "none" ? "text-[#9ca3af]" : "text-[#fbbf24]"
              }
            >
              {activeMode}
            </span>
          </span>
        )}
      </div>

      {error && (
        <p className="mb-3 text-xs text-[#f87171]">{error}</p>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {MODES.map(({ mode, label, magnitude, detail }) => {
          const isPending = pending === mode;
          const isActive = activeMode === mode && mode !== "none";
          return (
            <button
              key={mode}
              type="button"
              disabled={pending !== null}
              onClick={() => handleInject(mode, magnitude)}
              className={[
                "rounded border px-3 py-2 text-left transition-colors",
                "disabled:cursor-not-allowed disabled:opacity-50",
                isActive
                  ? "border-[#fbbf24] bg-[#1a1608]"
                  : "border-[#2a2f38] bg-[#0d1117] hover:border-[#4b5563]",
              ].join(" ")}
            >
              <span className="block text-sm text-[#e5e7eb]">
                {isPending ? "…" : label}
              </span>
              <span className="mt-0.5 block text-[10px] text-[#6b7280]">
                {detail}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
