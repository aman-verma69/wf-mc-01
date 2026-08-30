import { CampaignList } from "@/features/campaigns/CampaignList";
import { getMockCampaigns } from "@/lib/mock-data";

export default function CampaignsPage() {
  return (
    <div className="p-8 max-w-3xl">
      <p className="text-xs font-mono text-ink-300 mb-2">campaigns</p>
      <h1 className="font-display text-2xl italic text-ink-50 mb-1">Growth proposes, campaign executes.</h1>
      <p className="text-ink-300 text-sm mb-6 max-w-lg">
        growth_agent identifies who to reach; campaign_agent only ever sends through the
        notification service — never composes a payment.
      </p>
      <CampaignList campaigns={getMockCampaigns()} />
    </div>
  );
}
