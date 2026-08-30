import type { AgentChatResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export function sendAgentMessage(params: {
  agentKey: string;
  message: string;
  customerId: string;
  history: { role: string; content: string }[];
}): Promise<AgentChatResponse> {
  return post("/agents/chat", {
    agent_key: params.agentKey,
    message: params.message,
    customer_id: params.customerId,
    history: params.history,
  });
}

export function confirmCheckout(orderId: string, confirmedBy: string) {
  return post("/checkout/confirm", { order_id: orderId, confirmed_by: confirmedBy });
}

export function initiateRefund(razorpayPaymentId: string, amountPaise: number | null, reason: string) {
  return post("/payments/refund", {
    razorpay_payment_id: razorpayPaymentId,
    amount_paise: amountPaise,
    reason,
  });
}
