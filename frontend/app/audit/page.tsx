import { LedgerTape } from "@/features/audit/LedgerTape";
import { getMockAuditFeed } from "@/lib/mock-data";

export default function AuditPage() {
  return (
    <div className="p-8 max-w-2xl">
      <p className="text-xs font-mono text-ink-300 mb-2">ledger</p>
      <h1 className="font-display text-2xl italic text-ink-50 mb-1">The complete audit trail.</h1>
      <p className="text-ink-300 text-sm mb-6 max-w-lg">
        Every guardrail decision writes here, including the allowed ones. If an agent tried
        something and was stopped, it's on this tape.
      </p>
      <LedgerTape entries={getMockAuditFeed()} title="audit_log" />
    </div>
  );
}
