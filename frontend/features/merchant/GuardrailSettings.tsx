"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { Card, CardLabel } from "@/components/Card";
import { formatPaise } from "@/lib/format";

export function GuardrailSettings() {
  const [limitPaise, setLimitPaise] = useState(500000);
  const [requireConfirmation, setRequireConfirmation] = useState(true);
  const [saved, setSaved] = useState(false);

  return (
    <Card className="p-6 max-w-md">
      <CardLabel>Autonomous spend limit</CardLabel>
      <p className="text-xs text-ink-400 mt-1 mb-4">
        MAX_AUTONOMOUS_SPEND_PAISE — checkouts above this are parked in
        awaiting_confirmation until a human approves them.
      </p>

      <input
        type="range"
        min={10000}
        max={2000000}
        step={10000}
        value={limitPaise}
        onChange={(e) => { setLimitPaise(Number(e.target.value)); setSaved(false); }}
        className="w-full accent-brass"
      />
      <p className="mt-2 font-mono text-2xl text-ink-50 tabular-nums">{formatPaise(limitPaise)}</p>

      <label className="flex items-center gap-2 mt-5 text-sm text-ink-50">
        <input
          type="checkbox"
          checked={requireConfirmation}
          onChange={(e) => { setRequireConfirmation(e.target.checked); setSaved(false); }}
          className="accent-brass"
        />
        Require human confirmation above limit
      </label>
      {!requireConfirmation && (
        <p className="mt-1 text-xs text-blocked">
          Without this, orders above the limit are blocked outright rather than escalated.
        </p>
      )}

      <Button className="mt-5" onClick={() => setSaved(true)}>
        {saved ? "Saved" : "Save"}
      </Button>
      <p className="mt-2 text-[11px] text-ink-400">
        Wire this to a real settings endpoint — currently these values live only in
        backend/config/settings.py as env vars.
      </p>
    </Card>
  );
}
