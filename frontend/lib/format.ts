import type { PostmortemReport } from "./types";

export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatDuration(startedAt: string, endedAt: string | null): string {
  if (!endedAt) return "ongoing";
  const ms = new Date(endedAt).getTime() - new Date(startedAt).getTime();
  if (ms < 0) return "—";
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  if (min < 60) return rem > 0 ? `${min}m ${rem}s` : `${min}m`;
  const hr = Math.floor(min / 60);
  const remMin = min % 60;
  return remMin > 0 ? `${hr}h ${remMin}m` : `${hr}h`;
}

export function postmortemToMarkdown(
  incidentId: number,
  triggerType: string,
  postmortem: PostmortemReport,
): string {
  const lines = [
    `# Incident #${incidentId} Postmortem`,
    "",
    `**Trigger:** ${triggerType}`,
    "",
    "## Summary",
    postmortem.summary,
    "",
    "## Root Cause",
    postmortem.root_cause,
    "",
    "## Impact",
    postmortem.impact.description,
    `- Peak error rate: ${postmortem.impact.peak_error_rate}%`,
    `- Peak latency: ${postmortem.impact.peak_latency_ms} ms`,
    "",
    "## Timeline",
    ...postmortem.timeline.map(
      (e) => `- **${formatTimestamp(e.timestamp)}** — ${e.description}`,
    ),
    "",
    "## Action Items",
    ...postmortem.action_items.map((item) => `- ${item}`),
  ];
  return lines.join("\n");
}
