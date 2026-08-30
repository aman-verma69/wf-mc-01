/**
 * The backend currently exposes action endpoints (chat, confirm, refund)
 * but no GET/list endpoints for orders, disputes, campaigns, or the audit
 * log — see backend/api/v1/. This file stands in for those until you add
 * e.g. GET /api/v1/orders, GET /api/v1/audit. Swap each function body for
 * a real fetch() once that route exists; the shapes already match
 * lib/types.ts so no consuming component should need to change.
 */
import type { AuditEntry, CampaignProposal, Dispute, Order } from "./types";

export function getMockOrders(): Order[] {
  return [
    { id: "ord_8f2a", customerId: "cust_4471", amountPaise: 249900, status: "paid", createdByAgent: "buyer_agent", createdAt: "2026-08-30T09:12:00Z" },
    { id: "ord_8f2b", customerId: "cust_2201", amountPaise: 899000, status: "awaiting_confirmation", createdByAgent: "buyer_agent", createdAt: "2026-08-30T09:04:00Z" },
    { id: "ord_8f29", customerId: "cust_9981", amountPaise: 129900, status: "paid", createdByAgent: "buyer_agent", createdAt: "2026-08-30T08:51:00Z" },
    { id: "ord_8f26", customerId: "cust_1120", amountPaise: 45000, status: "refunded", createdByAgent: "buyer_agent", createdAt: "2026-08-30T08:20:00Z" },
    { id: "ord_8f22", customerId: "cust_7734", amountPaise: 320000, status: "failed", createdByAgent: "buyer_agent", createdAt: "2026-08-30T07:58:00Z" },
  ];
}

export function getMockDisputes(): Dispute[] {
  return [
    { id: "dsp_112", paymentId: "pay_9a01", status: "open", reasonCode: "goods_not_received", respondBy: "2026-09-02T00:00:00Z" },
    { id: "dsp_108", paymentId: "pay_8f31", status: "evidence_submitted", reasonCode: "duplicate", respondBy: "2026-08-31T00:00:00Z" },
  ];
}

export function getMockCampaigns(): CampaignProposal[] {
  return [
    { id: "cmp_31", proposedBy: "growth_agent", title: "Recover 3-day abandoned carts, ₹500+", audienceSize: 214, expectedRecoveryPaise: 1840000, status: "proposed" },
    { id: "cmp_30", proposedBy: "growth_agent", title: "Win-back: no purchase in 60 days", audienceSize: 802, expectedRecoveryPaise: 950000, status: "sent" },
  ];
}

export function getMockAuditFeed(): AuditEntry[] {
  return [
    { id: "a1", actor: "guardrail", action: "checkout.gate_check", decision: "allowed", reason: "Passed all guardrail checks", createdAt: "2026-08-30T09:12:00Z" },
    { id: "a2", actor: "payment_service", action: "payment.captured", decision: "captured", reason: null, createdAt: "2026-08-30T09:12:04Z" },
    { id: "a3", actor: "guardrail", action: "checkout.gate_check", decision: "escalated", reason: "Amount exceeds autonomous limit — human confirmation required", createdAt: "2026-08-30T09:04:00Z" },
    { id: "a4", actor: "guardrail", action: "checkout.gate_check", decision: "allowed", reason: "Passed all guardrail checks", createdAt: "2026-08-30T08:51:00Z" },
    { id: "a5", actor: "payment_service", action: "payment.refund_processed", decision: "refunded", reason: "Customer requested — size issue", createdAt: "2026-08-30T08:22:00Z" },
    { id: "a6", actor: "guardrail", action: "checkout.gate_check", decision: "blocked", reason: "Agent's delegation scope does not include checkout", createdAt: "2026-08-30T08:10:00Z" },
    { id: "a7", actor: "dispute_service", action: "dispute.created", decision: "allowed", reason: null, createdAt: "2026-08-30T07:40:00Z" },
  ];
}
