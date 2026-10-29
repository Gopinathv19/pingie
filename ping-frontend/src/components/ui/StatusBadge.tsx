import type { BotStatus, SourceStatus } from "@/lib/types";

const map: Record<BotStatus | SourceStatus, { label: string; cls: string }> = {
  live: { label: "Live", cls: "badge-ok" },
  draft: { label: "Draft", cls: "" },
  paused: { label: "Paused", cls: "badge-warn" },
  ready: { label: "Ready", cls: "badge-ok" },
  queued: { label: "Fetching", cls: "badge-accent" },
  indexing: { label: "Indexing", cls: "badge-accent" },
  failed: { label: "Failed", cls: "badge-danger" },
};

export function StatusBadge({ status }: { status: BotStatus | SourceStatus }) {
  const { label, cls } = map[status];
  return <span className={`badge ${cls}`}>{label}</span>;
}
