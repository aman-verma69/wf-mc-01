"use client";

import { Send } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/Button";
import { sendAgentMessage } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "I can help you find products and check out. What are you looking for?" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    if (!input.trim() || loading) return;
    const userMessage: ChatMessage = { role: "user", content: input };
    setMessages((m) => [...m, userMessage]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await sendAgentMessage({
        agentKey: "buyer",
        message: userMessage.content,
        customerId: "cust_demo",
        history: messages,
      });
      if (res.reply) {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: res.reply },
        ]);
      } else {
        setError("The agent returned an empty response.");
      }
      }
      catch (e) {
      setError(
        e instanceof Error
          ? `Couldn't reach the backend — ${e.message}`
          : "Couldn't reach the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[560px] rounded-md border border-border bg-surface">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <span className="text-sm font-medium text-ink-50">buyer_agent</span>
        <span className="text-[11px] font-mono text-ink-400">gpt-oss-20b</span>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-md px-3 py-2 text-sm leading-relaxed ${
                m.role === "user" ? "bg-brass/15 text-ink-50 border border-brass/30" : "bg-surface2 text-ink-50 border border-border"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && <p className="text-xs font-mono text-ink-400">buyer_agent is thinking…</p>}
        {error && (
          <div className="rounded-md border border-blocked/30 bg-blocked/10 px-3 py-2 text-xs text-blocked">
            {error}
          </div>
        )}
      </div>

      <div className="p-3 border-t border-border flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask about a product, or say what you'd like to buy…"
          className="flex-1 bg-ink border border-border rounded-sm px-3 py-2 text-sm text-ink-50 placeholder:text-ink-400 focus:border-brass outline-none"
        />
        <Button onClick={handleSend} disabled={loading}>
          <Send size={15} />
        </Button>
      </div>
    </div>
  );
}
