"use client";

import { LayoutGrid, MessageSquareText, Receipt, ShieldCheck, Megaphone, Workflow, ScrollText } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/buyer", label: "Buyer agent", icon: MessageSquareText },
  { href: "/payments", label: "Payments", icon: Receipt },
  { href: "/workflow", label: "Workflow", icon: Workflow },
  { href: "/merchant", label: "Guardrail", icon: ShieldCheck },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  { href: "/audit", label: "Ledger", icon: ScrollText },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 shrink-0 border-r border-border bg-surface flex flex-col">
      <div className="px-5 py-6 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-[3px] border border-brass flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-brass" />
          </div>
          <span className="font-display text-lg tracking-tight text-ink-50">Ledger</span>
        </div>
        <p className="mt-1 text-[11px] text-ink-300 font-mono">agentic commerce, on the record</p>
      </div>

      <nav className="flex-1 py-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-5 py-2.5 text-sm transition-colors border-l-2 ${
                active
                  ? "border-brass bg-surface2 text-ink-50"
                  : "border-transparent text-ink-300 hover:text-ink-50 hover:bg-surface2/60"
              }`}
            >
              <Icon size={16} strokeWidth={1.75} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-border">
        <p className="text-[11px] text-ink-400 font-mono leading-relaxed">
          agents run on gpt-oss-20b
          <br />
          payments via razorpay
        </p>
      </div>
    </aside>
  );
}
