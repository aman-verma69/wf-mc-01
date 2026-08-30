"use client";

import { useEffect, useState } from "react";

export function TopBar() {
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString("en-IN", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="h-14 shrink-0 border-b border-border bg-surface/60 backdrop-blur flex items-center justify-between px-6">
      <div className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-allowed" />
        <span className="text-xs font-mono text-ink-300">development · guardrail active</span>
      </div>
      <span className="text-xs font-mono text-ink-400 tabular-nums">{time || "--:--:--"} IST</span>
    </header>
  );
}
