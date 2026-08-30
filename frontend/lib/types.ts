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

export interface Product {
  id?: string | null;
  name: string;
  price?: number | string | null;
  currency?: string;
  image_url?: string | null;
  source?: string;
  product_url?: string | null;
  availability?: string;
  metadata?: Record<string, unknown>;
}

export interface AgentChatResponse {
  agent: string;
  reply: string;
  products: Product[];
  ok: boolean;
  error?: string | null;
}
