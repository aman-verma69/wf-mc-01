import { Card } from "@/components/Card";
import { StatusPill } from "@/components/StatusPill";
import { formatDateTime } from "@/lib/format";
import type { Dispute } from "@/lib/types";

export function DisputeList({ disputes }: { disputes: Dispute[] }) {
  if (disputes.length === 0) {
    return <p className="text-sm text-ink-400">No open disputes.</p>;
  }
  return (
    <Card className="divide-y divide-border">
      {disputes.map((d) => (
        <div key={d.id} className="px-4 py-3 flex items-center justify-between text-sm">
          <div>
            <p className="font-mono text-ink-50">{d.id}</p>
            <p className="text-xs text-ink-400">payment {d.paymentId} · {d.reasonCode?.replace(/_/g, " ")}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-escalated">respond by {formatDateTime(d.respondBy)}</span>
            <StatusPill status={d.status} />
          </div>
        </div>
      ))}
    </Card>
  );
}
