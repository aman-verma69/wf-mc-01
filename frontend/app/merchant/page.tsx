import { GuardrailSettings } from "@/features/merchant/GuardrailSettings";

export default function MerchantPage() {
  return (
    <div className="p-8 max-w-3xl">
      <p className="text-xs font-mono text-ink-300 mb-2">merchant</p>
      <h1 className="font-display text-2xl italic text-ink-50 mb-1">Set the gate's rules.</h1>
      <p className="text-ink-300 text-sm mb-6 max-w-lg">
        These are the only rules an agent cannot argue its way around.
      </p>
      <GuardrailSettings />
    </div>
  );
}
