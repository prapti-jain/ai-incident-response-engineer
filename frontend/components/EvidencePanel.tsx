import type { EvidenceItem } from "@/lib/types";
import { formatTimestamp } from "@/lib/format";

export function EvidenceRow({ item }: { item: EvidenceItem }) {
  return (
    <div className="rounded border border-[#2a2f38] bg-[#0d1117] p-3 font-mono text-[11px] leading-5">
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[#6b7280]">
        <span>{formatTimestamp(item.timestamp)}</span>
        <span>{item.service}</span>
        <span>{item.source}</span>
      </div>
      {item.source === "logs" ? (
        <div className="mt-1">
          <span
            className={
              item.level === "error" ? "text-[#f87171]" : "text-[#9ca3af]"
            }
          >
            [{item.level}]
          </span>{" "}
          <span className="text-[#c9d1d9]">{item.message}</span>
          {item.trace_id && (
            <div className="mt-1 text-[#6b7280]">trace: {item.trace_id}</div>
          )}
        </div>
      ) : (
        <div className="mt-1 text-[#c9d1d9]">
          {item.metric_name} = {item.value}
        </div>
      )}
    </div>
  );
}

type EvidenceIdsProps = {
  evidenceIds: number[];
  evidenceIndex: Map<number, EvidenceItem>;
  joinedEvidence?: EvidenceItem[];
  expandedIds: Set<number>;
  onToggle: (id: number) => void;
};

export function EvidenceIdsList({
  evidenceIds,
  evidenceIndex,
  joinedEvidence,
  expandedIds,
  onToggle,
}: EvidenceIdsProps) {
  const joinedMap = new Map(
    joinedEvidence?.map((item) => [item.id, item]) ?? [],
  );

  return (
    <div className="mt-2 space-y-1">
      <p className="text-[10px] uppercase tracking-widest text-[#6b7280]">
        Evidence ({evidenceIds.length})
      </p>
      <div className="flex flex-wrap gap-1.5">
        {evidenceIds.map((eid) => {
          const expanded = expandedIds.has(eid);
          return (
            <button
              key={eid}
              type="button"
              onClick={() => onToggle(eid)}
              className={[
                "rounded border px-2 py-0.5 font-mono text-[10px] transition-colors",
                expanded
                  ? "border-[#9ca3af] bg-[#1a1f27] text-[#e5e7eb]"
                  : "border-[#2a2f38] bg-[#0d1117] text-[#9ca3af] hover:border-[#4b5563]",
              ].join(" ")}
            >
              #{eid}
            </button>
          );
        })}
      </div>
      {evidenceIds
        .filter((eid) => expandedIds.has(eid))
        .map((eid) => {
          const item = joinedMap.get(eid) ?? evidenceIndex.get(eid);
          return (
            <div key={eid} className="mt-2">
              <p className="mb-1 text-[10px] text-[#6b7280]">
                Evidence #{eid}
              </p>
              {item ? (
                <EvidenceRow item={item} />
              ) : (
                <p className="text-xs text-[#fbbf24]">
                  Not in the sampled evidence window returned by the API
                  (incident may have more items than the 150-item sample).
                </p>
              )}
            </div>
          );
        })}
    </div>
  );
}
