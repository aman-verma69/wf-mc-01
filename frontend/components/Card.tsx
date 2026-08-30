import type { HTMLAttributes } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-md border border-border bg-surface ${className}`}
      {...props}
    />
  );
}

export function CardLabel({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] uppercase tracking-wider text-ink-300 font-mono">{children}</p>;
}
