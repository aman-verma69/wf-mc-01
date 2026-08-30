const STYLES: Record<string, string> = {
  allowed: "text-allowed bg-allowed/10 border-allowed/30",
  captured: "text-allowed bg-allowed/10 border-allowed/30",
  paid: "text-allowed bg-allowed/10 border-allowed/30",
  won: "text-allowed bg-allowed/10 border-allowed/30",
  sent: "text-allowed bg-allowed/10 border-allowed/30",
  approved: "text-allowed bg-allowed/10 border-allowed/30",

  escalated: "text-escalated bg-escalated/10 border-escalated/30",
  awaiting_confirmation: "text-escalated bg-escalated/10 border-escalated/30",
  open: "text-escalated bg-escalated/10 border-escalated/30",
  proposed: "text-escalated bg-escalated/10 border-escalated/30",
  evidence_submitted: "text-escalated bg-escalated/10 border-escalated/30",

  blocked: "text-blocked bg-blocked/10 border-blocked/30",
  failed: "text-blocked bg-blocked/10 border-blocked/30",
  lost: "text-blocked bg-blocked/10 border-blocked/30",
  cancelled: "text-blocked bg-blocked/10 border-blocked/30",

  refunded: "text-ink-300 bg-ink-300/10 border-ink-300/30",
  created: "text-ink-300 bg-ink-300/10 border-ink-300/30",
};

export function StatusPill({ status }: { status: string }) {
  const style = STYLES[status] ?? "text-ink-300 bg-ink-300/10 border-ink-300/30";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-mono uppercase tracking-wide ${style}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
