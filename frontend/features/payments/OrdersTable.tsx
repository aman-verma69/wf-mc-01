"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { StatusPill } from "@/components/StatusPill";
import { initiateRefund } from "@/lib/api";
import { formatDateTime, formatPaise } from "@/lib/format";
import type { Order } from "@/lib/types";

export function OrdersTable({ orders }: { orders: Order[] }) {
  const [refunding, setRefunding] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function handleRefund(order: Order) {
    setRefunding(order.id);
    setNote(null);
    try {
      await initiateRefund(order.id, order.amountPaise, "Merchant-initiated refund");
      setNote(`Refund initiated for ${order.id}.`);
    } catch (e) {
      setNote(e instanceof Error ? `Refund failed: ${e.message}` : "Refund failed.");
    } finally {
      setRefunding(null);
    }
  }

  return (
    <div>
      {note && <p className="mb-3 text-xs font-mono text-ink-300">{note}</p>}
      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-ink-400 border-b border-border">
              <th className="px-4 py-3 font-medium">Order</th>
              <th className="px-4 py-3 font-medium">Customer</th>
              <th className="px-4 py-3 font-medium">Amount</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {orders.map((o) => (
              <tr key={o.id}>
                <td className="px-4 py-3 font-mono text-ink-50">{o.id}</td>
                <td className="px-4 py-3 text-ink-300">{o.customerId}</td>
                <td className="px-4 py-3 font-mono text-ink-50 tabular-nums">{formatPaise(o.amountPaise)}</td>
                <td className="px-4 py-3"><StatusPill status={o.status} /></td>
                <td className="px-4 py-3 text-ink-400 font-mono text-xs">{formatDateTime(o.createdAt)}</td>
                <td className="px-4 py-3 text-right">
                  {o.status === "paid" && (
                    <Button variant="ghost" className="text-xs px-2 py-1" onClick={() => handleRefund(o)} disabled={refunding === o.id}>
                      {refunding === o.id ? "Refunding…" : "Refund"}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
