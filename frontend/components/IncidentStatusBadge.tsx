type Props = {
  status: string;
};

export default function IncidentStatusBadge({ status }: Props) {
  const isOpen = status === "open";
  return (
    <span
      className={[
        "inline-flex rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        isOpen
          ? "border border-[#fbbf24] bg-[#1a1608] text-[#fbbf24]"
          : "border border-[#374151] bg-[#0d1117] text-[#9ca3af]",
      ].join(" ")}
    >
      {status}
    </span>
  );
}
