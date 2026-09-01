type AgentChatResponse = { agent: string; reply: string; products: Array<{ name: string; price?: number | string | null; id?: string | null; currency?: string; image_url?: string | null; availability?: string }>; ok: boolean; error?: string | null };

export type Customer = { id: string; email: string; created_at: string; is_active: boolean; role: string };
export type Product = { id: string; merchant_id: string; sku: string; name: string; description: string; price_paise: number; currency: string; physical_quantity: number; reserved_quantity: number; available_quantity: number; is_active: boolean; created_at: string; updated_at: string };
export type CartItem = { product_id: string; name: string; quantity: number; unit_price_paise: number; currency: string };
export type Cart = { customer_id: string; items: CartItem[]; total_paise: number };
export type Order = { order_id: string; customer_id: string; status: string; amount_paise: number; currency: string; cart_snapshot: Record<string, unknown>; razorpay_order_id?: string | null };
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("fieldhouse_token") : null;
  const headers = new Headers(options.headers); headers.set("Content-Type", "application/json"); if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new ApiError(response.status, body.detail?.reason || body.detail || "Something went wrong"); }
  return response.json();
}
export const api = {
  register: (email: string, password: string) => request<Customer>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) => request<{ access_token: string; token_type: string }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<Customer>("/auth/me"), products: () => request<Product[]>("/products"), product: (id: string) => request<Product>(`/products/${id}`),
  cart: (customerId: string) => request<Cart>(`/customers/${customerId}/cart`),
  addToCart: (customerId: string, item: { product_id: string; name: string; quantity: number; unit_price_paise: number }) => request<Cart>(`/customers/${customerId}/cart/items`, { method: "POST", body: JSON.stringify(item) }),
  updateCart: (customerId: string, productId: string, quantity: number) => request<Cart>(`/customers/${customerId}/cart/items/${productId}`, { method: "PATCH", body: JSON.stringify({ quantity }) }),
  removeFromCart: (customerId: string, productId: string) => request<Cart>(`/customers/${customerId}/cart/items/${productId}`, { method: "DELETE" }),
  orders: (customerId: string) => request<Order[]>(`/customers/${customerId}/orders`),
  checkout: (customerId: string) => request<Record<string, unknown>>("/checkout/initiate", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ customer_id: customerId }) }),
  createProduct: (payload: { sku: string; name: string; description: string; price_paise: number; initial_stock: number }) => request<Product>("/products", { method: "POST", body: JSON.stringify(payload) }),
  adjustInventory: (productId: string, addQuantity: number) => request<Product>(`/products/${productId}/inventory`, { method: "PATCH", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ add_quantity: addQuantity }) }),
};
export function sendAgentMessage(params: { agentKey: string; message: string; customerId: string; history: { role: string; content: string }[] }) {
  return request<AgentChatResponse>("/agents/chat", { method: "POST", body: JSON.stringify({ agent_key: params.agentKey, message: params.message, customer_id: params.customerId }) });
}
export function initiateRefund(razorpayPaymentId: string, amountPaise: number | null, reason: string) {
  return request<Record<string, unknown>>("/payments/refund", { method: "POST", body: JSON.stringify({ razorpay_payment_id: razorpayPaymentId, amount_paise: amountPaise, reason }) });
}
export function confirmCheckout(orderId: string, confirmedBy: string) {
  return request<Record<string, unknown>>("/checkout/confirm", { method: "POST", body: JSON.stringify({ order_id: orderId, confirmed_by: confirmedBy }) });
}
export function formatPrice(paise: number, currency = "INR") { return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(paise / 100); }
