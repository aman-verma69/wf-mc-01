import { Card, CardLabel } from "@/components/Card";
import { LedgerTape } from "@/features/audit/LedgerTape";
import { formatPaise } from "@/lib/format";
import { getMockAuditFeed, getMockOrders } from "@/lib/mock-data";

export default function OverviewPage() {
  const orders = getMockOrders();
  const audit = getMockAuditFeed();

  const totalToday = orders.filter((o) => o.status === "paid").reduce((sum, o) => sum + o.amountPaise, 0);
  const gateCounts = audit.reduce(
    (acc, e) => {
      if (e.decision === "allowed") acc.allowed++;
      else if (e.decision === "blocked") acc.blocked++;
      else if (e.decision === "escalated") acc.escalated++;
      return acc;
    },
    { allowed: 0, blocked: 0, escalated: 0 }
  );

  return (
    <div className="p-8 max-w-6xl">
      <p className="text-xs font-mono text-ink-300 mb-2">overview</p>
      <h1 className="font-display text-3xl italic text-ink-50 mb-1">
        Every rupee your agents move, on the record.
      </h1>
      <p className="text-ink-300 text-sm mb-8 max-w-xl">
        Six agents act on behalf of your customers and your business. None of them touch Razorpay
        directly — every request passes through the guardrail gate first.
      </p>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <Card className="col-span-1 p-5">
          <CardLabel>Captured today</CardLabel>
          <p className="mt-2 font-mono text-3xl text-ink-50 tabular-nums">{formatPaise(totalToday)}</p>
          <p className="mt-1 text-xs text-ink-400">across {orders.filter((o) => o.status === "paid").length} orders</p>
        </Card>

        <Card className="col-span-2 p-5">
          <CardLabel>Guardrail decisions, last 24h</CardLabel>
          <div className="mt-3 flex items-end gap-6">
            <GateStat label="Allowed" value={gateCounts.allowed} color="text-allowed" />
            <GateStat label="Escalated" value={gateCounts.escalated} color="text-escalated" />
            <GateStat label="Blocked" value={gateCounts.blocked} color="text-blocked" />
          </div>
          <div className="mt-4 h-1.5 w-full rounded-full bg-ink-400/20 overflow-hidden flex">
            <div className="bg-allowed h-full" style={{ width: `${(gateCounts.allowed / audit.length) * 100}%` }} />
            <div className="bg-escalated h-full" style={{ width: `${(gateCounts.escalated / audit.length) * 100}%` }} />
            <div className="bg-blocked h-full" style={{ width: `${(gateCounts.blocked / audit.length) * 100}%` }} />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-4">
          <CardLabel>Recent orders</CardLabel>
          <Card className="divide-y divide-border">
            {orders.slice(0, 5).map((o) => (
              <div key={o.id} className="px-4 py-3 flex items-center justify-between text-sm">
                <div>
                  <p className="font-mono text-ink-50">{o.id}</p>
                  <p className="text-xs text-ink-400">{o.customerId} · {o.createdByAgent}</p>
                </div>
                <p className="font-mono text-ink-50 tabular-nums">{formatPaise(o.amountPaise)}</p>
              </div>
            ))}
          </Card>
        </div>

        <div className="col-span-1">
          <div className="mb-2"><CardLabel>Live feed</CardLabel></div>
          <LedgerTape entries={audit.slice(0, 5)} />
        </div>
      </div>
    </div>
  );
}

function GateStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <p className={`font-mono text-2xl tabular-nums ${color}`}>{value}</p>
      <p className="text-[11px] text-ink-400 uppercase tracking-wide mt-0.5">{label}</p>
    </div>
  );
}
