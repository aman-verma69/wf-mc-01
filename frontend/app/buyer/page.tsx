import { ChatPanel } from "@/features/buyer/ChatPanel";

export default function BuyerPage() {
  return (
    <div className="p-8 max-w-3xl">
      <p className="text-xs font-mono text-ink-300 mb-2">buyer agent</p>
      <h1 className="font-display text-2xl italic text-ink-50 mb-1">Shop, then check out.</h1>
      <p className="text-ink-300 text-sm mb-6 max-w-lg">
        This is the only agent with checkout in its delegation scope. Every request it makes
        still passes through the guardrail gate before Razorpay is touched.
      </p>
      <ChatPanel />
    </div>
  );
}
