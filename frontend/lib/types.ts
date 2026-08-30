export type GateDecision = "allowed" | "blocked" | "escalated";

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  decision: GateDecision | "captured" | "refunded";
  reason: string | null;
  createdAt: string;
}

export type OrderStatus = "created" | "awaiting_confirmation" | "paid" | "failed" | "refunded" | "cancelled";

export interface Order {
  id: string;
  customerId: string;
  amountPaise: number;
  status: OrderStatus;
  createdByAgent: string | null;
  createdAt: string;
}

export type DisputeStatus = "open" | "evidence_submitted" | "won" | "lost";

export interface Dispute {
  id: string;
  paymentId: string;
  status: DisputeStatus;
  reasonCode: string | null;
  respondBy: string;
}

export interface CampaignProposal {
  id: string;
  proposedBy: "growth_agent";
  title: string;
  audienceSize: number;
  expectedRecoveryPaise: number;
  status: "proposed" | "approved" | "sent";
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AgentChatResponse {
  agent: string;
  reply: string;
  ok: boolean;
  error?: string | null;
}
