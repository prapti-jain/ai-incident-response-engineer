"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import AppNav from "@/components/AppNav";
import { EvidenceIdsList } from "@/components/EvidencePanel";
import IncidentStatusBadge from "@/components/IncidentStatusBadge";
import {
  analyzeIncident,
  fetchIncident,
  fetchIncidentEvidence,
  generatePostmortem,
} from "@/lib/api";
import {
  formatDuration,
  formatTimestamp,
  postmortemToMarkdown,
} from "@/lib/format";
import type {
  AnalyzeResponse,
  CauseWithEvidence,
  EvidenceItem,
  Incident,
  PostmortemReport,
  RootCause,
} from "@/lib/types";

type Props = {
  incidentId: number;
};

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-[#2a2f38] bg-[#12161c] p-4">
      <h2 className="mb-3 text-xs uppercase tracking-widest text-[#6b7280]">
        {title}
      </h2>
      {children}
    </section>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  variant = "default",
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  variant?: "default" | "primary";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "rounded border px-3 py-1.5 text-xs transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary"
          ? "border-[#4b5563] bg-[#0d1117] text-[#e5e7eb] hover:border-[#9ca3af]"
          : "border-[#2a2f38] bg-[#0d1117] text-[#9ca3af] hover:border-[#4b5563]",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function PostmortemView({ postmortem }: { postmortem: PostmortemReport }) {
  return (
    <div className="space-y-4 text-sm text-[#c9d1d9]">
      <div>
        <h3 className="mb-1 text-[10px] uppercase tracking-widest text-[#6b7280]">
          Summary
        </h3>
        <p>{postmortem.summary}</p>
      </div>
      <div>
        <h3 className="mb-1 text-[10px] uppercase tracking-widest text-[#6b7280]">
          Root cause
        </h3>
        <p>{postmortem.root_cause}</p>
      </div>
      <div>
        <h3 className="mb-1 text-[10px] uppercase tracking-widest text-[#6b7280]">
          Impact
        </h3>
        <p>{postmortem.impact.description}</p>
        <p className="mt-1 font-mono text-xs text-[#9ca3af]">
          peak error rate: {postmortem.impact.peak_error_rate}% · peak latency:{" "}
          {postmortem.impact.peak_latency_ms} ms
        </p>
      </div>
      <div>
        <h3 className="mb-2 text-[10px] uppercase tracking-widest text-[#6b7280]">
          Timeline
        </h3>
        <ol className="space-y-2 border-l border-[#2a2f38] pl-4">
          {postmortem.timeline.map((entry, i) => (
            <li key={`${entry.timestamp}-${i}`} className="relative">
              <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-[#4b5563]" />
              <p className="font-mono text-[10px] text-[#6b7280]">
                {formatTimestamp(entry.timestamp)}
              </p>
              <p className="text-[#c9d1d9]">{entry.description}</p>
            </li>
          ))}
        </ol>
      </div>
      <div>
        <h3 className="mb-2 text-[10px] uppercase tracking-widest text-[#6b7280]">
          Action items
        </h3>
        <ul className="list-inside list-disc space-y-1 text-[#c9d1d9]">
          {postmortem.action_items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function CauseCard({
  cause,
  evidenceIndex,
  joinedEvidence,
  expandedIds,
  onToggleEvidence,
}: {
  cause: RootCause | CauseWithEvidence;
  evidenceIndex: Map<number, EvidenceItem>;
  joinedEvidence?: EvidenceItem[];
  expandedIds: Set<number>;
  onToggleEvidence: (id: number) => void;
}) {
  return (
    <div className="rounded border border-[#2a2f38] bg-[#0d1117] p-3">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-xs text-[#6b7280]">
          rank {cause.rank}
        </span>
      </div>
      <p className="mt-1 text-sm text-[#e5e7eb]">{cause.summary}</p>
      <p className="mt-2 text-xs text-[#9ca3af]">{cause.justification}</p>
      <EvidenceIdsList
        evidenceIds={cause.evidence_ids}
        evidenceIndex={evidenceIndex}
        joinedEvidence={
          "evidence" in cause && cause.evidence.length > 0
            ? cause.evidence
            : joinedEvidence
        }
        expandedIds={expandedIds}
        onToggle={onToggleEvidence}
      />
    </div>
  );
}

export default function IncidentDetail({ incidentId }: Props) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [evidenceIndex, setEvidenceIndex] = useState<
    Map<number, EvidenceItem>
  >(new Map());
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(
    null,
  );
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [generatingPm, setGeneratingPm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [inc, evidence] = await Promise.all([
        fetchIncident(incidentId),
        fetchIncidentEvidence(incidentId),
      ]);
      setIncident(inc);
      setEvidenceIndex(new Map(evidence.items.map((item) => [item.id, item])));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incident");
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleEvidence = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setActionError(null);
    try {
      const result = await analyzeIncident(incidentId);
      setAnalyzeResult(result);
      setIncident((prev) =>
        prev
          ? { ...prev, rca_report: result.rca_report }
          : prev,
      );
      const joined = new Map(
        result.all_cited_evidence.map((item) => [item.id, item]),
      );
      setEvidenceIndex((prev) => new Map([...prev, ...joined]));
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "RCA analysis failed",
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const handlePostmortem = async () => {
    setGeneratingPm(true);
    setActionError(null);
    try {
      const result = await generatePostmortem(incidentId);
      setIncident((prev) =>
        prev ? { ...prev, postmortem: result.postmortem } : prev,
      );
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Postmortem generation failed",
      );
    } finally {
      setGeneratingPm(false);
    }
  };

  const handleCopyMarkdown = async () => {
    if (!incident?.postmortem) return;
    const md = postmortemToMarkdown(
      incident.id,
      incident.trigger_type,
      incident.postmortem,
    );
    await navigator.clipboard.writeText(md);
    setCopyFeedback("Copied to clipboard");
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  const handleDownloadMarkdown = () => {
    if (!incident?.postmortem) return;
    const md = postmortemToMarkdown(
      incident.id,
      incident.trigger_type,
      incident.postmortem,
    );
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `incident-${incident.id}-postmortem.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center p-8 text-sm text-[#6b7280]">
        Loading incident…
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
        <p className="text-sm text-[#f87171]">{error ?? "Incident not found"}</p>
        <Link href="/incidents" className="text-xs text-[#9ca3af] hover:underline">
          ← Back to incidents
        </Link>
      </div>
    );
  }

  const causes: (RootCause | CauseWithEvidence)[] =
    analyzeResult?.causes ??
    incident.rca_report?.causes ??
    [];
  const hasRca = causes.length > 0;
  const joinedByRank = new Map(
    analyzeResult?.causes.map((c) => [c.rank, c.evidence]) ?? [],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4 lg:p-6">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-[#2a2f38] pb-4">
        <div>
          <Link
            href="/incidents"
            className="text-xs text-[#6b7280] hover:text-[#9ca3af]"
          >
            ← Incidents
          </Link>
          <h1 className="mt-1 text-lg font-medium tracking-tight text-[#e5e7eb]">
            Incident #{incident.id}
          </h1>
          <p className="mt-0.5 font-mono text-xs text-[#9ca3af]">
            {incident.trigger_type}
          </p>
        </div>
        <AppNav current="incidents" />
      </header>

      {actionError && (
        <div className="rounded border border-[#2a2f38] px-3 py-2 text-xs text-[#f87171]">
          {actionError}
        </div>
      )}

      <Panel title="Metadata">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-[#6b7280]">
              Status
            </dt>
            <dd className="mt-1">
              <IncidentStatusBadge status={incident.status} />
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-[#6b7280]">
              Duration
            </dt>
            <dd className="mt-1 text-[#c9d1d9]">
              {formatDuration(incident.started_at, incident.ended_at)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-[#6b7280]">
              Started
            </dt>
            <dd className="mt-1 text-[#c9d1d9]">
              {formatTimestamp(incident.started_at)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-[#6b7280]">
              Ended
            </dt>
            <dd className="mt-1 text-[#c9d1d9]">
              {incident.ended_at
                ? formatTimestamp(incident.ended_at)
                : "—"}
            </dd>
          </div>
        </dl>
      </Panel>

      <Panel title="Root cause analysis">
        {!hasRca ? (
          <div className="space-y-3">
            <p className="text-sm text-[#9ca3af]">
              No RCA report yet. Analysis uses Gemini and may take a few
              seconds.
            </p>
            <ActionButton
              variant="primary"
              onClick={handleAnalyze}
              disabled={analyzing}
            >
              {analyzing ? "Analyzing…" : "Run RCA Analysis"}
            </ActionButton>
          </div>
        ) : (
          <div className="space-y-3">
            {!incident.rca_report && analyzeResult && (
              <p className="text-xs text-[#4ade80]">Analysis complete</p>
            )}
            {causes.map((cause) => (
              <CauseCard
                key={cause.rank}
                cause={cause}
                evidenceIndex={evidenceIndex}
                joinedEvidence={joinedByRank.get(cause.rank)}
                expandedIds={expandedIds}
                onToggleEvidence={toggleEvidence}
              />
            ))}
            <ActionButton onClick={handleAnalyze} disabled={analyzing}>
              {analyzing ? "Re-analyzing…" : "Re-run RCA Analysis"}
            </ActionButton>
          </div>
        )}
      </Panel>

      <Panel title="Postmortem">
        {!incident.postmortem ? (
          <div className="space-y-3">
            <p className="text-sm text-[#9ca3af]">
              Generate a structured postmortem from the RCA and evidence.
            </p>
            <ActionButton
              variant="primary"
              onClick={handlePostmortem}
              disabled={!hasRca || generatingPm}
            >
              {generatingPm
                ? "Generating…"
                : "Generate Postmortem"}
            </ActionButton>
            {!hasRca && (
              <p className="text-xs text-[#6b7280]">
                Run RCA analysis first
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <PostmortemView postmortem={incident.postmortem} />
            <div className="flex flex-wrap items-center gap-2 border-t border-[#2a2f38] pt-4">
              <ActionButton onClick={handleCopyMarkdown}>
                Copy as Markdown
              </ActionButton>
              <ActionButton onClick={handleDownloadMarkdown}>
                Download .md
              </ActionButton>
              {copyFeedback && (
                <span className="text-xs text-[#4ade80]">{copyFeedback}</span>
              )}
              <ActionButton
                onClick={handlePostmortem}
                disabled={generatingPm}
              >
                {generatingPm ? "Regenerating…" : "Regenerate"}
              </ActionButton>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}
