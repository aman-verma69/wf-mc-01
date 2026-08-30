import { Card } from "@/components/Card";
import { StatusPill } from "@/components/StatusPill";
import { formatPaise } from "@/lib/format";
import type { CampaignProposal } from "@/lib/types";

export function CampaignList({ campaigns }: { campaigns: CampaignProposal[] }) {
  return (
    <div className="space-y-3">
      {campaigns.map((c) => (
        <Card key={c.id} className="p-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-ink-50">{c.title}</p>
            <p className="text-xs text-ink-400 mt-0.5 font-mono">
              proposed by {c.proposedBy} · {c.audienceSize} customers · est. recovery {formatPaise(c.expectedRecoveryPaise)}
            </p>
          </div>
          <StatusPill status={c.status} />
        </Card>
      ))}
    </div>
  );
}
