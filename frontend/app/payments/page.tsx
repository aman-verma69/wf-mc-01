import { CardLabel } from "@/components/Card";
import { DisputeList } from "@/features/payments/DisputeList";
import { OrdersTable } from "@/features/payments/OrdersTable";
import { getMockDisputes, getMockOrders } from "@/lib/mock-data";

export default function PaymentsPage() {
  const orders = getMockOrders();
  const disputes = getMockDisputes();

  return (
    <div className="p-8 max-w-5xl space-y-8">
      <div>
        <p className="text-xs font-mono text-ink-300 mb-2">payments</p>
        <h1 className="font-display text-2xl italic text-ink-50 mb-1">Orders and refunds.</h1>
        <p className="text-ink-300 text-sm max-w-lg">
          Status here reflects Razorpay webhooks, not client callbacks — an order only shows
          Paid once payment.captured has actually arrived.
        </p>
      </div>

      <div>
        <div className="mb-2"><CardLabel>Orders</CardLabel></div>
        <OrdersTable orders={orders} />
      </div>

      <div>
        <div className="mb-2"><CardLabel>Disputes</CardLabel></div>
        <DisputeList disputes={disputes} />
      </div>
    </div>
  );
}
