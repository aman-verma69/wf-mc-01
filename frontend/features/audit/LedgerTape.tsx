import { formatTime } from "@/lib/format";
import type { AuditEntry } from "@/lib/types";

const DOT: Record<string, string> = {
  allowed: "bg-allowed",
  captured: "bg-allowed",
  escalated: "bg-escalated",
  blocked: "bg-blocked",
  refunded: "bg-ink-300",
};

export function LedgerTape({ entries, title = "Ledger tape" }: { entries: AuditEntry[]; title?: string }) {
  return (
    <div className="rounded-md border border-border bg-surface2 overflow-hidden">
      <div className="torn-edge bg-surface2" />
      <div className="px-4 py-2.5 border-b border-border/60 flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wider text-ink-300 font-mono">{title}</span>
        <span className="text-[10px] text-ink-400 font-mono">live</span>
      </div>
      <ol className="divide-y divide-border/40 max-h-[440px] overflow-y-auto">
        {entries.map((e) => (
          <li key={e.id} className="px-4 py-3 font-mono text-xs">
            <div className="flex items-center gap-2 text-ink-400">
              <span className={`w-1.5 h-1.5 rounded-full ${DOT[e.decision] ?? "bg-ink-300"}`} />
              <span>{formatTime(e.createdAt)}</span>
              <span className="text-ink-400/60">·</span>
              <span>{e.actor}</span>
            </div>
            <p className="mt-1 text-ink-50">{e.action}</p>
            {e.reason && <p className="mt-0.5 text-ink-300 leading-relaxed">{e.reason}</p>}
          </li>
        ))}
      </ol>
      <div className="torn-edge bg-surface2 rotate-180" />
    </div>
  );
}
